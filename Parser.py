import ply.yacc as yacc
import ply.lex as lex
from Lexer_Ply import tokens, lexer as analizador_lexico, errores_lexicos as errores_lexicos_globales, \
    generar_bitacora_html, encontrar_columna
import tkinter as tk
from tkinter import filedialog
import re


class CompiladorContext:
    def __init__(self):
        self.reset()

    def reset(self):
        self.tabla_simbolos = {}
        self.funciones = {}
        self.codigo_tres_direcciones = []
        self.temporal_counter = 0
        self.label_counter = 0
        self.contexto_actual = "global"  # Para futura expansión de scopes
        self.errores = []
        self.codigo_optimizado = []
        self.codigo_cpp = ""
        # Tipos conocidos, pueden expandirse
        self.tipos_validos = {'int', 'float', 'string', 'bool', 'void'}  # void para funciones sin retorno

    def optimizar_codigo(self):
        optimizador = Optimizador(self.codigo_tres_direcciones)
        self.codigo_optimizado = optimizador.optimizar()
        return self.codigo_optimizado

    def generar_cpp(self):
        generador = GeneradorCPP(self.codigo_optimizado if self.codigo_optimizado else self.codigo_tres_direcciones,
                                 self)
        self.codigo_cpp = generador.generar()
        return self.codigo_cpp

    def nuevo_temporal(self):
        self.temporal_counter += 1
        return f"t{self.temporal_counter}"

    def nueva_etiqueta(self):
        self.label_counter += 1
        return f"L{self.label_counter}"

    def emitir(self, codigo, comentario=""):
        # Si el código es None (debido a un error previo), no emitir nada.
        if codigo is None:
            return

        linea_codigo = ""
        if isinstance(codigo, str):
            linea_codigo = codigo
        elif isinstance(codigo, tuple):
            # Esta lógica es para procesar tuplas de sentencia que vienen de bloques (if/while/for)
            op = codigo[0]
            if op == 'asignacion':  # ('asignacion', var_name, temp_name_expr)
                linea_codigo = f"{codigo[1]} = {codigo[2]}"
            elif op == 'declaracion_variable':  # ('declaracion_variable', var_name, var_type, None o (val,tipo) )
                # La declaración directa ya emite, esto es si se re-emite una tupla de info
                linea_codigo = f"declare {codigo[2]} {codigo[1]}"
                if len(codigo) > 3 and codigo[3] is not None:
                    val_inicial, _ = codigo[3]
                    linea_codigo += f" = {val_inicial}"
            elif op == 'imprimir':  # ('imprimir', valor_a_imprimir, tipo_del_valor)
                linea_codigo = f"imprimir {codigo[1]}"
            elif op == 'leer':  # ('leer', var_name)
                linea_codigo = f"leer {codigo[1]}"
            elif op == 'retornar':  # ('retornar', valor_retorno, tipo_retorno)
                linea_codigo = f"RETURN {codigo[1]}"
            else:
                # Si es una tupla no reconocida aquí, es probable que sea un string que se empaquetó accidentalmente.
                # O una estructura que esta función no espera.
                # Por seguridad, convertir a string, pero idealmente las reglas deben emitir strings formateados.
                print(f"[WARN] Emitiendo tupla no procesada directamente: {codigo}")
                linea_codigo = str(codigo)
        else:
            self.errores.append(f"Error interno: Intento de emitir tipo no string/tupla: {type(codigo)}")
            return

        if comentario:
            self.codigo_tres_direcciones.append(f"{linea_codigo.ljust(30)} # {comentario}")
        else:
            self.codigo_tres_direcciones.append(linea_codigo)

    def agregar_simbolo(self, nombre, tipo, lineno, col_num, valor=None, es_param=False, func_name=None):
        scope_key = f"{func_name}::{nombre}" if func_name and self.contexto_actual != "global" else nombre

        if self.contexto_actual == "global":
            if nombre in self.tabla_simbolos and not self.tabla_simbolos[nombre].get(
                    'es_parametro_de_func'):  # Permitir shadowing de global por param
                if nombre in self.funciones:  # Conflicto con nombre de función
                    self.errores.append(
                        f"Error semántico en línea {lineno}, columna {col_num}: El identificador '{nombre}' ya está declarado como una función.")
                    return False
                self.errores.append(
                    f"Error semántico en línea {lineno}, columna {col_num}: La variable '{nombre}' ya ha sido declarada en el ámbito global.")
                return False
        else:  # Dentro de una función
            if scope_key in self.tabla_simbolos:
                self.errores.append(
                    f"Error semántico en línea {lineno}, columna {col_num}: La variable '{nombre}' ya ha sido declarada en la función '{func_name}'.")
                return False

        self.tabla_simbolos[scope_key] = {'tipo': tipo, 'valor': valor, 'scope': self.contexto_actual,
                                          'es_parametro_de_func': es_param, 'func_name': func_name}
        if tipo.startswith('array'):  # e.g. array(int, 10)
            self.tipos_validos.add(tipo)  # Registrar tipos de array dinámicamente
        return True

    def agregar_simbolo_temporal(self, nombre_temporal, tipo):
        # Usado para registrar el tipo de los temporales
        if nombre_temporal not in self.tabla_simbolos:
            self.tabla_simbolos[nombre_temporal] = {'tipo': tipo, 'valor': None, 'scope': 'temporal'}
        # Si ya existe (raro para un nuevo temporal), podríamos actualizar su tipo si es más específico
        elif self.tabla_simbolos[nombre_temporal]['tipo'] == 'auto_infer':
            self.tabla_simbolos[nombre_temporal]['tipo'] = tipo

    def obtener_simbolo(self, nombre, func_name=None):
        if func_name and self.contexto_actual != "global":  # Buscar en scope local de función primero
            scope_key = f"{func_name}::{nombre}"
            if scope_key in self.tabla_simbolos:
                return self.tabla_simbolos[scope_key]
        # Buscar en global o si no se encontró en local
        if nombre in self.tabla_simbolos:
            return self.tabla_simbolos.get(nombre)
        return None

    def actualizar_valor_simbolo(self, nombre, valor, func_name=None):
        simbolo = self.obtener_simbolo(nombre, func_name)
        if simbolo:
            simbolo['valor'] = valor
            return True
        return False

    def registrar_funcion(self, nombre, tipo_retorno, params_tuplas, lineno, col_num):
        if nombre in self.funciones:
            self.errores.append(
                f"Error semántico en línea {lineno}, columna {col_num}: La función '{nombre}' ya ha sido declarada.")
            return False
        if nombre in self.tabla_simbolos:  # Conflicto con variable global
            self.errores.append(
                f"Error semántico en línea {lineno}, columna {col_num}: El identificador '{nombre}' ya está declarado como una variable global.")
            return False

        self.funciones[nombre] = {'tipo_retorno': tipo_retorno, 'params': params_tuplas, 'declarada_en_linea': lineno}
        # También añadir a tabla de símbolos para evitar colisiones de nombres con variables globales
        self.tabla_simbolos[nombre] = {'tipo': 'func_signature', 'valor': f"{tipo_retorno}({params_tuplas})",
                                       'scope': 'global'}
        return True

    def inferir_tipo_operacion(self, tipo1_str, op, tipo2_str, lineno_op, col_op):
        # Reglas de promoción y compatibilidad de tipos
        # Esta es una simplificación. Un sistema de tipos real es más complejo.
        type_priority = {'error': -1, 'bool': 0, 'int': 1, 'float': 2, 'string': 3}  # String solo con ciertos ops

        # Manejar tipos de error primero
        if tipo1_str.startswith('error_') or tipo2_str.startswith('error_'):
            return 'error_operando_invalido'

        # Operaciones aritméticas (+, -, *, /)
        if op in ['+', '-', '*', '/']:
            if tipo1_str == 'string' and tipo2_str == 'string' and op == '+':  # Concatenación
                return 'string'
            if tipo1_str in ['int', 'float'] and tipo2_str in ['int', 'float']:
                if op == '/' and tipo1_str == 'int' and tipo2_str == 'int':  # División entera podría dar float
                    return 'float'  # Asumir división flotante
                return 'float' if tipo1_str == 'float' or tipo2_str == 'float' else 'int'
            else:
                self.errores.append(
                    f"Error semántico en línea {lineno_op}, columna {col_op}: Operación aritmética '{op}' inválida entre tipos '{tipo1_str}' y '{tipo2_str}'.")
                return 'error_tipo_incompatible'

        # Operación Módulo (%)
        if op == '%':
            if tipo1_str == 'int' and tipo2_str == 'int':
                return 'int'
            else:
                self.errores.append(
                    f"Error semántico en línea {lineno_op}, columna {col_op}: Operación módulo '%' solo válida entre enteros. Tipos: '{tipo1_str}', '{tipo2_str}'.")
                return 'error_tipo_incompatible'

        # Operaciones de comparación (>, <, >=, <=, ==, !=)
        if op in ['>', '<', '>=', '<=', '==', '!=']:
            # Permitir comparación entre int/float, o string/string, o bool/bool
            if (tipo1_str in ['int', 'float'] and tipo2_str in ['int', 'float']) or \
                    (tipo1_str == 'string' and tipo2_str == 'string') or \
                    (tipo1_str == 'bool' and tipo2_str == 'bool'):
                return 'bool'
            # Permitir comparar null o undefined (si se añaden)
            else:
                self.errores.append(
                    f"Error semántico en línea {lineno_op}, columna {col_op}: Comparación '{op}' inválida entre tipos '{tipo1_str}' y '{tipo2_str}'.")
                return 'error_tipo_incompatible'

        # Operaciones lógicas (y, o)
        if op in ['y', 'o']:
            if tipo1_str == 'bool' and tipo2_str == 'bool':
                return 'bool'
            else:
                self.errores.append(
                    f"Error semántico en línea {lineno_op}, columna {col_op}: Operador lógico '{op}' requiere operandos booleanos. Tipos: '{tipo1_str}', '{tipo2_str}'.")
                return 'error_tipo_incompatible'

        # Operador lógico (no) - se maneja en p_expresion_unaria

        self.errores.append(
            f"Error semántico en línea {lineno_op}, columna {col_op}: Operador '{op}' desconocido o no implementado para tipos '{tipo1_str}', '{tipo2_str}'.")
        return 'error_operador_desconocido'

    def obtener_tipo_de_expresion_tupla(self, expr_tupla, default_tipo='error_tipo_desconocido'):
        if isinstance(expr_tupla, tuple) and len(expr_tupla) == 2:
            return expr_tupla[1]
        # Si no es una tupla (valor, tipo), podría ser un error o un literal directo que no pasó por la producción correcta.
        # Esto es una contingencia, idealmente todas las expresiones producen la tupla.
        print(f"[WARN] Se esperaba tupla (valor,tipo), se recibió: {expr_tupla}. Asumiendo tipo '{default_tipo}'.")
        return default_tipo


# Instanciar contexto global
contexto = CompiladorContext()


class GeneradorCPP:
    def __init__(self, codigo_optimizado_o_original, comp_context):
        self.codigo_3addr = codigo_optimizado_o_original
        self.contexto_compilador = comp_context  # Acceso al contexto para tabla de símbolos, etc.
        self.includes = set(['<iostream>', '<vector>', '<string>', '<iomanip>'])
        self.function_definitions = []
        self.main_body_lines = []
        self.declared_variables_main = set()
        self.declared_variables_func = {}  # func_name -> set of var names
        self.temporaries_to_declare_main = {}  # name: type
        self.temporaries_to_declare_func = {}  # func_name -> {name: type}

    def generar(self):
        self._procesar_codigo()
        return self._generar_codigo_completo()

    def _procesar_codigo(self):
        current_function_body = []
        current_function_name = None
        in_function_def = False

        # Primero, escanear para declaraciones de array globales para C++
        # (Esto es una simplificación, la gestión de scopes debería ser más robusta)
        cpp_global_declarations = []
        for simbolo, detalles in self.contexto_compilador.tabla_simbolos.items():
            if detalles['scope'] == 'global' and detalles['tipo'].startswith('array('):
                # e.g. array(int, 10) for 'arr'
                match = re.match(r'array\((\w+),\s*(\d+)\)', detalles['tipo'])
                if match:
                    base_type_str = self._map_type_to_cpp(match.group(1))
                    size = match.group(2)
                    # Evitar redeclarar si ya está en _procesar_codigo (aunque aquí es para globales)
                    if simbolo not in self.declared_variables_main:  # Usamos declared_variables_main por simplicidad
                        cpp_global_declarations.append(f"{base_type_str} {simbolo}[{size}];")
                        self.declared_variables_main.add(simbolo)

        for linea_num, linea_raw in enumerate(self.codigo_3addr):
            linea = linea_raw.split('#')[0].strip()  # Quitar comentarios y espacios
            if not linea:
                continue

            if linea.startswith("INICIO_PROGRAMA") or linea.startswith("FIN_PROGRAMA"):
                continue

            if linea.startswith("FUNC"):  # e.g. FUNC miFuncion:
                current_function_name = linea.split()[1].replace(':', '').strip()
                self.declared_variables_func[current_function_name] = set()
                self.temporaries_to_declare_func[current_function_name] = {}

                func_info = self.contexto_compilador.funciones.get(current_function_name)
                if not func_info:
                    # Esto sería un error interno si el parser permitió esto
                    self.contexto_compilador.errores.append(
                        f"Error C++ Gen: Información no encontrada para función {current_function_name}")
                    # Usar una firma por defecto para intentar continuar
                    self.function_definitions.append(f"void {current_function_name}() {{ // Error: Info no encontrada")
                else:
                    ret_type_str = self._map_type_to_cpp(func_info['tipo_retorno'])
                    params_cpp = []
                    for p_tipo, p_nombre in func_info['params']:
                        params_cpp.append(f"{self._map_type_to_cpp(p_tipo)} {p_nombre}")
                        # Registrar parámetros como declarados en el scope de la función
                        self.declared_variables_func[current_function_name].add(p_nombre)

                    self.function_definitions.append(
                        f"{ret_type_str} {current_function_name}({', '.join(params_cpp)}) {{")
                in_function_def = True
                continue
            elif linea.startswith("END_FUNC"):
                # Declarar temporales de la función al inicio de su cuerpo
                if current_function_name and current_function_name in self.temporaries_to_declare_func:
                    temp_decls = []
                    for temp_var, temp_type_str in self.temporaries_to_declare_func[current_function_name].items():
                        if temp_var not in self.declared_variables_func[current_function_name]:  # No redeclarar
                            temp_decls.append(f"    {self._map_type_to_cpp(temp_type_str)} {temp_var};")
                    self.function_definitions.extend(temp_decls)

                self.function_definitions.extend(current_function_body)
                self.function_definitions.append("}")
                in_function_def = False
                current_function_name = None
                current_function_body = []
                continue
            elif linea.startswith("RETURN"):  # e.g. RETURN t1
                val_retorno = linea.split('RETURN')[1].strip()
                (current_function_body if in_function_def else self.main_body_lines).append(
                    f"    return {val_retorno};")
                continue

            # Procesamiento de líneas dentro de una función o en main
            target_body = current_function_body if in_function_def else self.main_body_lines
            target_declared_vars = self.declared_variables_func.get(current_function_name,
                                                                    set()) if in_function_def else self.declared_variables_main
            target_temp_to_declare = self.temporaries_to_declare_func.get(current_function_name,
                                                                          {}) if in_function_def else self.temporaries_to_declare_main

            if linea.startswith("declare "):  # declare tipo var o declare array tipo var[size]
                parts = linea.split()
                # parts[0] es 'declare'
                if parts[1] == "array":  # declare array int arr[10]
                    # tipo_base var_name[size]
                    declared_type_str = self._map_type_to_cpp(parts[2])
                    # var_name[size] -> var_name
                    array_name_full = parts[3]  # arr[10]
                    array_name = array_name_full.split('[')[0]
                    if array_name not in target_declared_vars and not array_name.startswith('t'):
                        # La declaración de arrays globales ya se hizo, esto es para main/funciones
                        # Si es global, self.declared_variables_main ya lo tiene.
                        # Aquí es para declaraciones dentro de main o funciones (si se permite)
                        if not (current_function_name is None and array_name in self.declared_variables_main):
                            target_body.append(f"    {declared_type_str} {array_name_full};")
                            target_declared_vars.add(array_name)
                else:  # declare tipo var
                    declared_type_str = self._map_type_to_cpp(parts[1])
                    declared_var = parts[2]
                    if declared_var not in target_declared_vars and not declared_var.startswith('t'):
                        target_body.append(f"    {declared_type_str} {declared_var};")
                        target_declared_vars.add(declared_var)

                    if len(parts) > 3 and parts[3] == '=':  # ... = val
                        initial_value = parts[4]
                        # Si es string literal, necesita comillas en C++
                        simbolo_var = self.contexto_compilador.obtener_simbolo(declared_var, current_function_name)
                        if simbolo_var and simbolo_var['tipo'] == 'string' and not initial_value.startswith('"'):
                            initial_value = f'"{initial_value}"'
                        target_body.append(f"    {declared_var} = {initial_value};")
                continue

            if "if not" in linea:  # if not cond_var goto etiqueta
                parts = linea.split()
                cond_var = parts[2]
                etiqueta = parts[-1]
                target_body.append(f"    if (!({cond_var})) goto {etiqueta};")
            elif linea.endswith(":"):  # Etiqueta:
                target_body.append(linea)  # Sin indentación para etiquetas
            elif linea.startswith("goto "):  # goto etiqueta
                target_body.append(f"    {linea};")
            elif linea.startswith("imprimir "):
                value_to_print = linea.split('imprimir', 1)[1].strip()
                # Chequear si es un booleano para usar std::boolalpha
                # Necesitamos el tipo real de value_to_print
                tipo_val = self._determinar_tipo_cpp_expr(value_to_print, current_function_name)
                if tipo_val == 'bool':
                    target_body.append(f'    std::cout << std::boolalpha << {value_to_print} << std::endl;')
                elif tipo_val == 'std::string' and not (
                        value_to_print.startswith('"') and value_to_print.endswith('"')):
                    # Si es una variable string, no necesita comillas extra. Si es un literal ya las tiene.
                    # Esta heurística es para el caso de que el 3AC tenga "imprimir mi_cadena_literal" sin comillas
                    # pero el parser debería añadir las comillas para literales de cadena.
                    simbolo = self.contexto_compilador.obtener_simbolo(value_to_print, current_function_name)
                    if not simbolo:  # Es un literal que no tiene comillas
                        target_body.append(f'    std::cout << "{value_to_print}" << std::endl;')
                    else:  # Es una variable
                        target_body.append(f'    std::cout << {value_to_print} << std::endl;')
                else:
                    target_body.append(f'    std::cout << {value_to_print} << std::endl;')

            elif linea.startswith("leer "):
                var_to_read = linea.split('leer', 1)[1].strip()
                target_body.append(f'    std::cin >> {var_to_read};')

            elif "call" in linea:  # tX = call func, [args] OR call func, [args]
                assign_var_cpp = None
                if '=' in linea:
                    assign_part, call_part = linea.split('=', 1)
                    assign_var_3addr = assign_part.strip()
                    call_str = call_part.strip()

                    # Determinar tipo del temporal asignado a partir del tipo de retorno de la función
                    func_name_call = call_str.split('call')[1].strip().split(',')[0].strip()
                    func_info = self.contexto_compilador.funciones.get(func_name_call)
                    ret_type = 'auto'  # Default
                    if func_info:
                        ret_type = self._map_type_to_cpp(func_info['tipo_retorno'])
                    else:  # Función no encontrada (e.g. print, etc. o error)
                        self.contexto_compilador.errores.append(
                            f"Advertencia C++ Gen: Función '{func_name_call}' no encontrada en el contexto para determinar tipo de retorno de '{assign_var_3addr}'. Asumiendo 'auto'.")

                    target_temp_to_declare[assign_var_3addr] = ret_type
                    assign_var_cpp = assign_var_3addr
                else:  # Llamada sin asignación
                    call_str = linea

                # Extraer nombre de función y argumentos
                # call func_name, [arg1, arg2]
                actual_call_part = call_str.split('call', 1)[1].strip()  # func_name, [arg1, arg2]
                func_name_call, args_3addr_str_with_brackets = actual_call_part.split(',', 1)
                func_name_call = func_name_call.strip()
                args_3addr_str = args_3addr_str_with_brackets.strip().lstrip('[').rstrip(']')

                args_list_cpp = [a.strip() for a in args_3addr_str.split(',') if a.strip()] if args_3addr_str else []

                cpp_call = f"{func_name_call}({', '.join(args_list_cpp)})"
                if assign_var_cpp:
                    target_body.append(f"    {assign_var_cpp} = {cpp_call};")
                else:
                    target_body.append(f"    {cpp_call};")

            elif "=" in linea:  # Asignaciones generales: var = expr, tX = expr, arr[tidx] = tval
                lhs, rhs = linea.split('=', 1)
                lhs = lhs.strip()
                rhs = rhs.strip()

                # Si LHS es un temporal, necesitamos declarar su tipo
                if lhs.startswith('t') and lhs not in target_temp_to_declare:
                    # El tipo del temporal debería haberse registrado por el parser
                    simbolo_temp = self.contexto_compilador.obtener_simbolo(
                        lhs)  # Temporales son "globales" en tabla simbolos
                    if simbolo_temp:
                        target_temp_to_declare[lhs] = self._map_type_to_cpp(simbolo_temp['tipo'])
                    else:  # Fallback si el tipo no se registró
                        target_temp_to_declare[lhs] = self._determinar_tipo_cpp_expr(rhs, current_function_name)

                # Si LHS es una variable no declarada y no es temporal (debería haber sido declarada explícita o implícitamente)
                elif not lhs.startswith('t') and lhs not in target_declared_vars and '[' not in lhs:
                    # Esto podría ser una variable que se declaró implícitamente en 3AC pero no en C++ aún
                    # O un error si la declaración implícita no se manejó bien.
                    # Asumimos que el parser ya validó y añadió a tabla de símbolos.
                    simbolo_lhs = self.contexto_compilador.obtener_simbolo(lhs, current_function_name)
                    if simbolo_lhs:
                        tipo_lhs_cpp = self._map_type_to_cpp(simbolo_lhs['tipo'])
                        # Declarar al inicio del scope actual (main o función)
                        declaration_line = f"    {tipo_lhs_cpp} {lhs};"
                        if in_function_def:
                            # Insertar al inicio de current_function_body si no es un temporal ya declarado
                            if not any(decl.strip().endswith(f" {lhs};") for decl in current_function_body):
                                current_function_body.insert(0, declaration_line)
                        else:
                            if not any(decl.strip().endswith(f" {lhs};") for decl in self.main_body_lines):
                                self.main_body_lines.insert(0, declaration_line)  # Declarar al inicio de main
                        target_declared_vars.add(lhs)
                    else:
                        self.contexto_compilador.errores.append(
                            f"Error C++ Gen: Variable '{lhs}' usada sin declarar y no se pudo inferir/encontrar en tabla de símbolos.")

                # Si el RHS es una cadena literal y LHS es de tipo string, asegurar comillas
                simbolo_lhs_check = self.contexto_compilador.obtener_simbolo(lhs.split('[')[0],
                                                                             current_function_name)  # Para arr[idx]
                if simbolo_lhs_check and simbolo_lhs_check['tipo'] == 'string':
                    if not (rhs.startswith('"') and rhs.endswith('"')) and not self.contexto_compilador.obtener_simbolo(
                            rhs, current_function_name) and not rhs.startswith('t'):
                        # Si RHS no es comillado, no es símbolo, no es temporal -> es un literal de string que perdió comillas
                        rhs = f'"{rhs}"'

                target_body.append(f"    {lhs} = {rhs};")

            else:  # Líneas no reconocidas explícitamente
                target_body.append(f"    // {linea} (línea 3AC no procesada directamente)")

        # Insertar declaraciones globales al inicio del archivo C++
        self.function_definitions = cpp_global_declarations + self.function_definitions

    def _map_type_to_cpp(self, tipo_lenguaje):
        if tipo_lenguaje == 'int': return 'int'
        if tipo_lenguaje == 'float': return 'float'
        if tipo_lenguaje == 'string': return 'std::string'
        if tipo_lenguaje == 'bool': return 'bool'
        if tipo_lenguaje == 'void': return 'void'  # Para tipo de retorno de funciones
        if tipo_lenguaje is None: return 'void'  # Default si no hay tipo de retorno
        # Para tipos de array como 'array(int, 10)', el generador maneja la sintaxis C++ [size]
        # así que aquí solo necesitamos el tipo base.
        match = re.match(r'array\((\w+)(?:,\s*\d+)?\)', tipo_lenguaje)
        if match:
            return self._map_type_to_cpp(match.group(1))  # Mapear recursivamente el tipo base

        # Si es un tipo de error o desconocido, usar 'auto' o marcar error
        if tipo_lenguaje and tipo_lenguaje.startswith('error_'):
            self.contexto_compilador.errores.append(
                f"Advertencia C++ Gen: Tipo de lenguaje '{tipo_lenguaje}' no mapeable directamente, usando 'auto'.")
            return 'auto'

        return 'auto'  # Fallback para tipos desconocidos o no manejados

    def _determinar_tipo_cpp_expr(self, expr_str, current_function_name=None):
        # 1. Buscar en tabla de símbolos
        simbolo = self.contexto_compilador.obtener_simbolo(expr_str, current_function_name)
        if simbolo:
            return simbolo['tipo']  # Devuelve el tipo base del lenguaje

        # 2. Inferir de literales - DETECCIÓN CORREGIDA
        # Verificar primero si es una cadena entre comillas dobles
        if len(expr_str) >= 2 and expr_str.startswith('"') and expr_str.endswith('"'):
            return 'string'  # Tipo base del lenguaje, no 'std::string'

        # Luego verificar booleanos
        if expr_str.lower() == "true" or expr_str.lower() == "false":
            return 'bool'

        # Finalmente verificar números
        if re.fullmatch(r'\d+', expr_str):
            return 'int'
        if re.fullmatch(r'\d+\.\d*|\d*\.\d+', expr_str):
            return 'float'

        # 3. Heurísticas para expresiones
        if any(op in expr_str for op in ['+', '-', '*', '/']):
            if '.' in expr_str or '/' in expr_str:
                return 'float'
            return 'int'
        if any(op in expr_str for op in ['>', '<', '==', '!=', '>=', '<=', 'y', 'o', 'no']):
            return 'bool'

        return 'auto'

    def _generar_codigo_completo(self):
        codigo_final_cpp = []
        for inc in sorted(list(self.includes)):
            codigo_final_cpp.append(f"#include {inc}")
        codigo_final_cpp.append("\nusing namespace std;\n")

        codigo_final_cpp.extend(self.function_definitions)  # Incluye globales y funciones
        codigo_final_cpp.append("\nint main() {")

        # Declarar temporales de main
        temps_decl_main = []
        for temp_var, temp_type_str in self.temporaries_to_declare_main.items():
            if temp_var not in self.declared_variables_main:  # No redeclarar
                temps_decl_main.append(f"    {self._map_type_to_cpp(temp_type_str)} {temp_var};")
        codigo_final_cpp.extend(temps_decl_main)

        # Cuerpo de main
        codigo_final_cpp.extend(self.main_body_lines)

        codigo_final_cpp.append("    return 0;")
        codigo_final_cpp.append("}")
        return "\n".join(codigo_final_cpp)


class Optimizador:
    def __init__(self, codigo_tres_direcciones):
        self.codigo_original = codigo_tres_direcciones
        self.codigo_optimizado = []

    def optimizar(self):
        # Copia para no modificar el original directamente si se reintenta
        self.codigo_optimizado = self.codigo_original[:]

        # Aplicar optimizaciones. Se pueden aplicar múltiples pasadas.
        # Por ahora, una pasada de cada una.
        # Nota: El orden de las optimizaciones puede importar.

        # TODO: Implementar un bucle que repita las optimizaciones hasta que no haya más cambios.
        # for _ in range(MAX_PASSES):
        #     prev_code = self.codigo_optimizado[:]
        #     self._propagar_constantes()
        #     self._eliminar_subexpresiones_comunes()
        #     # self._eliminar_codigo_muerto() # Necesita análisis de flujo de datos
        #     if prev_code == self.codigo_optimizado:
        #         break

        self._propagar_constantes_y_plegado()
        self._eliminar_subexpresiones_comunes()
        # La eliminación de código muerto es más compleja y requiere análisis de flujo.
        # Una forma simple (pero no completa) sería eliminar asignaciones a temporales
        # que no se usan después. El generador C++ ya evita declarar temps no usados.

        return self.codigo_optimizado

    def _propagar_constantes_y_plegado(self):
        # Realiza propagación de constantes y plegado de constantes simple.
        # Ejemplo: x = 5; y = x + 2; -> y = 7; (si x no se modifica entretanto)
        # Ejemplo: t1 = 2 + 3; -> t1 = 5;

        const_map = {}  # var_name -> valor_constante_str
        codigo_nuevo = []

        for linea_raw in self.codigo_optimizado:
            linea = linea_raw.split('#')[0].strip()  # Ignorar comentarios
            if not linea:
                codigo_nuevo.append(linea_raw)  # Mantener líneas vacías o solo comentarios
                continue

            # Sustituir variables por sus valores constantes en el lado derecho
            # Esto es delicado con regex, hacerlo con cuidado.
            # Usar word boundaries (\b) para evitar sustituciones parciales.
            linea_modificada = linea
            for var, val_str in const_map.items():
                linea_modificada = re.sub(r'\b' + re.escape(var) + r'\b', val_str, linea_modificada)

            # Analizar la línea modificada
            if '=' in linea_modificada and not linea_modificada.startswith("if") and not "call" in linea_modificada:
                lhs, rhs = [p.strip() for p in linea_modificada.split('=', 1)]

                # Intentar plegado de constantes (evaluación de expresiones constantes)
                # ¡PRECAUCIÓN CON EVAL! Solo para expresiones aritméticas muy simples.
                # Un parser de expresiones sería más seguro.
                try:
                    # Solo intentar eval si rhs parece una expresión aritmética simple de números
                    if re.fullmatch(r'[\d\s\.\+\-\*/%()]+', rhs) and not re.search(r'[a-zA-Z_]', rhs):
                        # No permitir funciones matemáticas de Python como sqrt(), etc.
                        if any(kw in rhs for kw in ['import', 'def', 'class', 'lambda', '__']):  # Lista negra simple
                            raise ValueError("Expresión no segura para eval")

                        eval_result = eval(rhs)  # Evaluar la expresión

                        # Formatear el resultado consistentemente
                        if isinstance(eval_result, float):
                            rhs_evaluado = str(eval_result)
                        elif isinstance(eval_result, int):
                            rhs_evaluado = str(eval_result)
                        # Añadir bool si es necesario, aunque eval de 'true' no funciona directamente.
                        # Los booleanos ya deberían estar como 'true'/'false'
                        else:  # Otros tipos no esperados aquí
                            rhs_evaluado = rhs  # No cambiar

                        # Si el plegado cambió el rhs, actualizarlo
                        if rhs_evaluado != rhs:
                            linea_modificada = f"{lhs} = {rhs_evaluado}"
                            rhs = rhs_evaluado  # Actualizar rhs para el registro en const_map

                except Exception:  # eval falló o expresión no segura
                    pass  # Mantener rhs como estaba

                # Actualizar mapa de constantes si lhs es una variable y rhs es un literal simple
                if re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', lhs):  # lhs es una variable simple
                    if re.fullmatch(r'-?\d+', rhs) or \
                            re.fullmatch(r'-?\d+(\.\d+)?', rhs) or \
                            (rhs.startswith('"') and rhs.endswith('"')) or \
                            rhs.lower() in ["true", "false"]:
                        const_map[lhs] = rhs
                    else:  # Si rhs no es un literal, la variable lhs deja de ser constante conocida
                        if lhs in const_map:
                            del const_map[lhs]

                codigo_nuevo.append(linea_modificada + linea_raw[len(linea):])  # Añadir comentario original si existía
            else:  # Líneas sin asignación (labels, jumps, calls, print, etc.)
                codigo_nuevo.append(linea_modificada + linea_raw[len(linea):])

        self.codigo_optimizado = codigo_nuevo

    def _eliminar_subexpresiones_comunes(self):
        # Elimina cálculos redundantes de la misma expresión.
        # Ejemplo: a = b * c; ... ; d = b * c; -> temp = b * c; a = temp; ...; d = temp;
        # Esta es una versión local (bloque básico), una global es más compleja.

        expr_to_temp = {}  # expr_str -> temp_var_name
        codigo_nuevo = []

        for linea_raw in self.codigo_optimizado:
            linea = linea_raw.split('#')[0].strip()
            comentario_original = linea_raw[len(linea):]

            if '=' in linea and not linea.startswith("if") and "call" not in linea and '[' not in linea.split('=')[
                0]:  # asignación simple
                lhs, rhs = [p.strip() for p in linea.split('=', 1)]

                # Ignorar si el lhs es un array (a[i] = ...) o si rhs es un solo operando (a = b)
                # Nos interesan rhs como 'op1 + op2'
                if '[' in lhs or not any(op in rhs for op in ['+', '-', '*', '/', '%', 'y', 'o', '>', '<']):
                    codigo_nuevo.append(linea_raw)
                    # Si a = b, y b es un temp de una expr común, podemos hacer a = expr_to_temp[b] si b estuviera en rhs.
                    # Pero por ahora, nos centramos en a = expr
                    if re.fullmatch(r'[a-zA-Z_][a-zA-Z0-9_]*', rhs) and rhs in expr_to_temp.values():
                        # Esto es una asignación var1 = var2, donde var2 ya es un temp de una CSE
                        # Podríamos intentar propagar más, pero es complejo.
                        pass  # Mantener por ahora.
                    else:  # Si la expr es un literal o variable, podría invalidar futuras CSE
                        # si esta variable se usa en otra expr.
                        # ej: x = 10. Si luego hay 'a + x', ya no es la misma expr que 'a + t_prev_x_val'.
                        # Por simplicidad, no manejamos estas invalidaciones complejas aquí.
                        pass

                elif rhs in expr_to_temp:
                    # Subexpresión común encontrada
                    temp_existente = expr_to_temp[rhs]
                    # No añadir nueva línea si lhs es el mismo temporal que ya almacena la expresión
                    if lhs != temp_existente:
                        codigo_nuevo.append(f"{lhs} = {temp_existente}{comentario_original}")
                    else:  # Es la misma asignación original, mantenerla (o la primera que la creó)
                        codigo_nuevo.append(linea_raw)  # Mantener la original que define el temp
                else:
                    # Nueva expresión, registrarla (solo si lhs es un temporal o una variable que podría ser usada así)
                    # Considerar que solo los temporales son buenos candidatos para reemplazar expresiones.
                    # Si lhs es una variable normal, y luego se reasigna, expr_to_temp[rhs] apuntaría a algo obsoleto.
                    # Por ahora, si lhs es un temporal, es un buen candidato.
                    if lhs.startswith('t'):
                        expr_to_temp[rhs] = lhs
                    codigo_nuevo.append(linea_raw)
            else:
                codigo_nuevo.append(linea_raw)
        self.codigo_optimizado = codigo_nuevo


# --- Definición del Parser PLY ---
start = 'programa'

precedence = (
    ('right', 'IGUAL'),
    ('left', 'O'),
    ('left', 'Y'),
    ('right', 'NO'),
    ('nonassoc', 'MENOR', 'MENOR_IGUAL', 'MAYOR', 'MAYOR_IGUAL', 'IGUAL_IGUAL', 'DIFERENTE'),
    ('left', 'MAS', 'MENOS'),
    ('left', 'MULT', 'DIV', 'MOD'),
    ('right', 'UMENOS'),  # Menos unario
    ('left', 'CORCHETE_IZQ', 'CORCHETE_DER'),  # Acceso a array
    ('left', 'PARENTESIS_IZQ', 'PARENTESIS_DER')  # Agrupación
)


# --- Reglas de la Gramática ---

def p_programa(p):
    """
    programa : sentencias_opt
    """
    contexto.emitir("INICIO_PROGRAMA", "Inicio del programa")
    # p[1] contiene la lista de sentencias (o None si está vacío)
    # Las sentencias ya deberían haber emitido su propio código.
    # Si p[1] es una lista de tuplas de info (como ('asignacion',...)), y queremos emitirlas aquí:
    if p[1]:  # Si hay sentencias
        for stmt_info_tuple in p[1]:
            if stmt_info_tuple:  # Puede haber Nones por errores
                # Esta emisión es redundante si las reglas de sentencia ya emiten.
                # contexto.emitir(stmt_info_tuple)
                pass
    contexto.emitir("FIN_PROGRAMA", "Fin del programa")
    p[0] = ('programa', p[1])


def p_asignacion_opt(p):
    """
    asignacion_opt : asignacion
                   |
    """
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = None


def p_sentencias_opt(p):
    """
    sentencias_opt : sentencias
                   |
    """
    if len(p) == 2:
        p[0] = p[1]
    else:
        p[0] = []  # Lista vacía si no hay sentencias


def p_sentencias(p):
    """
    sentencias : sentencia NEWLINE sentencias
               | sentencia NEWLINE
               | sentencia
    """
    if len(p) == 4:
        p[0] = [p[1]] + p[3] if p[1] else p[3]
    elif len(p) == 3:
        p[0] = [p[1]] if p[1] else []
    else:
        p[0] = [p[1]] if p[1] else []



def p_sentencia(p):
    """
    sentencia : asignacion
              | imprimir
              | condicion
              | mientras
              | para
              | retornar
              | declaracion_funcion
              | declaracion_variable
              | declaracion_array
              | leer
              | llamada_funcion_simple
    """
    p[0] = p[1]  # p[1] es la tupla de información de la sentencia o None si hubo error


def p_tipo_dato(p):
    """
    tipo_dato : INT_TYPE
              | FLOAT_TYPE
              | STRING_TYPE
              | BOOL_TYPE
    """
    p[0] = p[1]


def p_declaracion_variable(p):
    """
    declaracion_variable : tipo_dato IDENTIFICADOR
                         | tipo_dato IDENTIFICADOR IGUAL expresion
    """
    var_type = p[1]
    var_name = p[2]
    lineno = p.lineno(2)
    col_num = encontrar_columna(analizador_lexico.lexdata, p.lexpos(2))

    if not contexto.agregar_simbolo(var_name, var_type, lineno, col_num,
                                    func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None):
        p[0] = None  # Error al agregar símbolo
        return

    contexto.emitir(f"declare {var_type} {var_name}", f"Declarar variable {var_name} tipo {var_type}")

    if len(p) == 5:  # Con asignación: tipo_dato IDENTIFICADOR IGUAL expresion
        expr_val_str, expr_tipo_str = p[4]

        if expr_tipo_str.startswith('error_'):
            contexto.errores.append(
                f"Error semántico en línea {p.lineno(4)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(4))}: Expresión inválida para inicializar '{var_name}'.")
            p[0] = ('declaracion_variable', var_name, var_type, None)  # Declaración sin inicialización válida
            return

        # Verificación de compatibilidad de tipos para asignación inicial
        # Permitir int -> float. Para otros, deben ser exactos.
        if var_type != expr_tipo_str and not (var_type == 'float' and expr_tipo_str == 'int'):
            contexto.errores.append(
                f"Error semántico en línea {lineno}, columna {col_num}: Tipo incompatible en inicialización de '{var_name}'. Se esperaba '{var_type}' pero se obtuvo '{expr_tipo_str}'.")
            # Continuar con la declaración pero sin la asignación de valor en 3AC para el valor erróneo
        else:
            temp_init = contexto.nuevo_temporal()
            contexto.emitir(f"{temp_init} = {expr_val_str}", f"Valor inicial para {var_name}")
            contexto.emitir(f"{var_name} = {temp_init}", f"Asignar valor inicial a {var_name}")
            contexto.actualizar_valor_simbolo(var_name, expr_val_str,
                                              func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None)

        p[0] = ('declaracion_variable', var_name, var_type, (expr_val_str, expr_tipo_str))
    else:  # Sin asignación
        p[0] = ('declaracion_variable', var_name, var_type, None)


def p_asignacion(p):
    """
    asignacion : IDENTIFICADOR IGUAL expresion
               | IDENTIFICADOR CORCHETE_IZQ expresion CORCHETE_DER IGUAL expresion
    """
    # TODO: Refactorizar para reducir complejidad si es posible.
    line_num_id = p.lineno(1)
    col_num_id = encontrar_columna(analizador_lexico.lexdata, p.lexpos(1))

    if len(p) == 4:  # IDENTIFICADOR IGUAL expresion
        var_name = p[1]
        expr_val_str, expr_tipo_str = p[3]

        if expr_tipo_str.startswith('error_'):
            contexto.errores.append(
                f"Error semántico en línea {p.lineno(3)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(3))}: Expresión inválida en asignación a '{var_name}'.")
            p[0] = None
            return

        simbolo = contexto.obtener_simbolo(var_name,
                                           func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None)
        if not simbolo:  # Declaración implícita
            # Permitir declaración implícita solo si es una variable simple (no array element)
            # y si el tipo de la expresión es válido.
            if expr_tipo_str in contexto.tipos_validos and expr_tipo_str not in ['void']:
                if contexto.agregar_simbolo(var_name, expr_tipo_str, line_num_id, col_num_id,
                                            func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None):
                    contexto.emitir(f"declare {expr_tipo_str} {var_name}", f"Declaración implícita de {var_name}")
                    simbolo = contexto.obtener_simbolo(var_name,
                                                       func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None)  # Obtener el nuevo símbolo
                else:  # Falló al agregar símbolo (e.g. colisión de nombre con función)
                    p[0] = None
                    return
            else:
                contexto.errores.append(
                    f"Error semántico en línea {line_num_id}, columna {col_num_id}: Variable '{var_name}' no declarada y no se puede inferir un tipo válido de la expresión ('{expr_tipo_str}').")
                p[0] = None
                return

        # Verificación de tipo para la asignación
        var_original_tipo = simbolo['tipo']
        if var_original_tipo != expr_tipo_str and not (var_original_tipo == 'float' and expr_tipo_str == 'int'):
            contexto.errores.append(
                f"Error semántico en línea {line_num_id}, columna {col_num_id}: Asignación de tipo incompatible a '{var_name}'. Variable es '{var_original_tipo}', se intentó asignar '{expr_tipo_str}'.")
            # No emitir la asignación si los tipos son incompatibles (excepto int->float)
            p[0] = ('asignacion', var_name, None)  # Indica asignación fallida por tipo
            return

        temp_assign = contexto.nuevo_temporal()
        contexto.emitir(f"{temp_assign} = {expr_val_str}", f"Calcular valor para {var_name}")
        contexto.emitir(f"{var_name} = {temp_assign}", f"Asignar a {var_name}")
        contexto.actualizar_valor_simbolo(var_name, expr_val_str,
                                          func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None)
        p[0] = ('asignacion', var_name, temp_assign)

    else:  # Asignación a elemento de array: IDENTIFICADOR [ expresion_idx ] = expresion_val
        array_name = p[1]
        idx_val_str, idx_tipo_str = p[3]
        assign_val_str, assign_tipo_str = p[6]

        simbolo_array = contexto.obtener_simbolo(array_name,
                                                 func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None)
        if not simbolo_array or not simbolo_array['tipo'].startswith('array('):
            contexto.errores.append(
                f"Error semántico en línea {line_num_id}, columna {col_num_id}: '{array_name}' no es un array o no ha sido declarado.")
            p[0] = None
            return

        if idx_tipo_str != 'int':
            contexto.errores.append(
                f"Error semántico en línea {p.lineno(3)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(3))}: El índice del array '{array_name}' debe ser un entero, se obtuvo '{idx_tipo_str}'.")
            p[0] = None
            return

        if assign_tipo_str.startswith('error_'):
            contexto.errores.append(
                f"Error semántico en línea {p.lineno(6)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(6))}: Expresión inválida para asignar al elemento del array '{array_name}'.")
            p[0] = None
            return

        # Verificar tipo de elemento del array
        # Ejemplo tipo array: "array(int, 10)"
        match_tipo_array = re.match(r'array\((\w+),', simbolo_array['tipo'])
        if not match_tipo_array:
            contexto.errores.append(
                f"Error semántico en línea {line_num_id}, columna {col_num_id}: Formato de tipo de array inválido para '{array_name}'.")
            p[0] = None
            return

        tipo_elemento_array = match_tipo_array.group(1)
        if tipo_elemento_array != assign_tipo_str and not (tipo_elemento_array == 'float' and assign_tipo_str == 'int'):
            contexto.errores.append(
                f"Error semántico en línea {p.lineno(6)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(6))}: Tipo incompatible para el elemento del array '{array_name}'. Se esperaba '{tipo_elemento_array}', se obtuvo '{assign_tipo_str}'.")
            p[0] = None
            return

        temp_idx = contexto.nuevo_temporal()
        contexto.emitir(f"{temp_idx} = {idx_val_str}", f"Calcular índice para {array_name}")
        temp_val = contexto.nuevo_temporal()
        contexto.emitir(f"{temp_val} = {assign_val_str}", f"Calcular valor para {array_name}[{idx_val_str}]")
        contexto.emitir(f"{array_name}[{temp_idx}] = {temp_val}", f"Asignar a elemento de array")
        p[0] = ('asignacion_array', array_name, temp_idx, temp_val)


def p_leer(p):
    """
    leer : LEER PARENTESIS_IZQ IDENTIFICADOR PARENTESIS_DER
    """
    var_name = p[3]
    lineno = p.lineno(1)
    col_num = encontrar_columna(analizador_lexico.lexdata, p.lexpos(1))
    simbolo = contexto.obtener_simbolo(var_name,
                                       func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None)
    if not simbolo:
        contexto.errores.append(
            f"Error semántico en línea {lineno}, columna {col_num}: Variable '{var_name}' no declarada, no se puede usar en 'leer'.")
        p[0] = None
        return
    if simbolo['tipo'].startswith('array('):
        contexto.errores.append(
            f"Error semántico en línea {lineno}, columna {col_num}: No se puede leer directamente en un array completo '{var_name}'. Use un índice.")
        p[0] = None
        return

    contexto.emitir(f"leer {var_name}", f"Leer entrada para {var_name}")
    p[0] = ('leer', var_name)


def p_imprimir(p):
    """
    imprimir : IMPRIMIR PARENTESIS_IZQ expresion PARENTESIS_DER
    """
    expr_val_str, expr_tipo_str = p[3]
    if expr_tipo_str.startswith('error_'):
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(3)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(3))}: Expresión inválida en 'imprimir'.")
        p[0] = None
        return

    contexto.emitir(f"imprimir {expr_val_str}", f"Imprimir valor (tipo: {expr_tipo_str})")
    p[0] = ('imprimir', expr_val_str, expr_tipo_str)


def p_expresion_logica(p):
    """
    expresion : expresion Y expresion
              | expresion O expresion
    """
    val1_str, tipo1_str = p[1]
    op = p[2]
    val3_str, tipo3_str = p[3]
    lineno_op = p.lineno(2)
    col_op = encontrar_columna(analizador_lexico.lexdata, p.lexpos(2))

    if tipo1_str.startswith('error_') or tipo3_str.startswith('error_'):
        p[0] = (contexto.nuevo_temporal(), 'error_operando_invalido')
        # El error específico ya se habrá reportado en la subexpresión
        return

    tipo_resultado = contexto.inferir_tipo_operacion(tipo1_str, op, tipo3_str, lineno_op, col_op)
    if tipo_resultado.startswith('error_'):
        p[0] = (contexto.nuevo_temporal(), tipo_resultado)  # Propagar error
        return

    temp = contexto.nuevo_temporal()
    contexto.emitir(f"{temp} = {val1_str} {op} {val3_str}",
                    f"Operación lógica: {tipo1_str} {op} {tipo3_str} -> {tipo_resultado}")
    contexto.agregar_simbolo_temporal(temp, tipo_resultado)
    p[0] = (temp, tipo_resultado)


def p_expresion_binaria(p):
    """
    expresion : expresion MAS expresion
              | expresion MENOS expresion
              | expresion MULT expresion
              | expresion DIV expresion
              | expresion MOD expresion
              | expresion MAYOR expresion
              | expresion MENOR expresion
              | expresion MAYOR_IGUAL expresion
              | expresion MENOR_IGUAL expresion
              | expresion IGUAL_IGUAL expresion
              | expresion DIFERENTE expresion
    """
    val1_str, tipo1_str = p[1]
    op = p[2]
    val3_str, tipo3_str = p[3]
    lineno_op = p.lineno(2)
    col_op = encontrar_columna(analizador_lexico.lexdata, p.lexpos(2))

    if tipo1_str.startswith('error_') or tipo3_str.startswith('error_'):
        p[0] = (contexto.nuevo_temporal(), 'error_operando_invalido')
        return

    tipo_resultado = contexto.inferir_tipo_operacion(tipo1_str, op, tipo3_str, lineno_op, col_op)
    if tipo_resultado.startswith('error_'):
        p[0] = (contexto.nuevo_temporal(), tipo_resultado)
        return

    temp = contexto.nuevo_temporal()
    contexto.emitir(f"{temp} = {val1_str} {op} {val3_str}",
                    f"Operación binaria: {tipo1_str} {op} {tipo3_str} -> {tipo_resultado}")
    contexto.agregar_simbolo_temporal(temp, tipo_resultado)
    p[0] = (temp, tipo_resultado)


def p_expresion_unaria(p):
    """
    expresion : MENOS expresion %prec UMENOS
              | NO expresion
    """
    op = p[1]  # MENOS o NO
    val_expr_str, tipo_expr_str = p[2]
    lineno_op = p.lineno(1)
    col_op = encontrar_columna(analizador_lexico.lexdata, p.lexpos(1))

    if tipo_expr_str.startswith('error_'):
        p[0] = (contexto.nuevo_temporal(), 'error_operando_invalido')
        return

    tipo_resultado = 'error_desconocido'
    if op == '-':  # UMENOS
        if tipo_expr_str in ['int', 'float']:
            tipo_resultado = tipo_expr_str
        else:
            contexto.errores.append(
                f"Error semántico en línea {lineno_op}, columna {col_op}: Operador menos unario '-' solo aplicable a int o float, no a '{tipo_expr_str}'.")
            tipo_resultado = 'error_tipo_incompatible'
    elif op.lower() == 'no':  # NO lógico
        if tipo_expr_str == 'bool':
            tipo_resultado = 'bool'
        else:
            contexto.errores.append(
                f"Error semántico en línea {lineno_op}, columna {col_op}: Operador lógico 'no' solo aplicable a bool, no a '{tipo_expr_str}'.")
            tipo_resultado = 'error_tipo_incompatible'

    if tipo_resultado.startswith('error_'):
        p[0] = (contexto.nuevo_temporal(), tipo_resultado)
        return

    temp = contexto.nuevo_temporal()
    contexto.emitir(f"{temp} = {op} {val_expr_str}",
                    f"Operación unaria {op} sobre ({tipo_expr_str}) -> {tipo_resultado}")
    contexto.agregar_simbolo_temporal(temp, tipo_resultado)
    p[0] = (temp, tipo_resultado)


def p_expresion_group(p):
    """
    expresion : PARENTESIS_IZQ expresion PARENTESIS_DER
    """
    p[0] = p[2]  # Devuelve la tupla (valor_str, tipo_str) de la expresión interna


def p_expresion_primaria(p):
    """
    expresion : IDENTIFICADOR
              | NUMERO
              | CADENA
              | BOOLEANO
    """
    token_type = p.slice[1].type
    token_val = p[1]
    lineno = p.lineno(1)
    col_num = encontrar_columna(analizador_lexico.lexdata, p.lexpos(1))

    if token_type == 'IDENTIFICADOR':
        simbolo = contexto.obtener_simbolo(token_val,
                                           func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None)
        if simbolo:
            # Verificar si es una función usada como valor (no permitido sin llamada)
            if simbolo['tipo'] == 'func_signature':
                contexto.errores.append(
                    f"Error semántico en línea {lineno}, columna {col_num}: El nombre de función '{token_val}' no puede usarse como valor directamente. ¿Quizás quiso llamarla con '()'? ")
                p[0] = (token_val, 'error_uso_funcion_como_valor')
            else:
                p[0] = (token_val, simbolo['tipo'])
        else:
            contexto.errores.append(
                f"Error semántico en línea {lineno}, columna {col_num}: Variable '{token_val}' no declarada.")
            p[0] = (token_val, 'error_variable_no_declarada')
    elif token_type == 'NUMERO':
        tipo = 'float' if isinstance(token_val, float) else 'int'
        p[0] = (str(token_val), tipo)
    elif token_type == 'CADENA':
        # Asegurar que la cadena para 3AC esté entre comillas si no lo está ya (debería estarlo desde el lexer)
        val_str = str(token_val)
        if not (val_str.startswith('"') and val_str.endswith('"')):
            val_str = f'"{val_str}"'  # El lexer ya quita comillas, aquí las reponemos para el 3AC
        p[0] = (val_str, 'string')
    elif token_type == 'BOOLEANO':
        p[0] = (str(token_val).lower(), 'bool')


def p_llamada_funcion_expr(p):
    """
    expresion : IDENTIFICADOR PARENTESIS_IZQ argumentos PARENTESIS_DER
    """
    func_name = p[1]
    args_tuplas = p[3]  # Lista de tuplas (val_str, tipo_str)
    lineno = p.lineno(1)
    col_num = encontrar_columna(analizador_lexico.lexdata, p.lexpos(1))

    func_info = contexto.funciones.get(func_name)
    if not func_info:
        contexto.errores.append(
            f"Error semántico en línea {lineno}, columna {col_num}: Función '{func_name}' no declarada.")
        p[0] = (contexto.nuevo_temporal(), 'error_funcion_no_declarada')
        return

    # Validar argumentos
    params_def = func_info['params']  # Lista de (tipo_param, nombre_param)
    if len(args_tuplas) != len(params_def):
        contexto.errores.append(
            f"Error semántico en línea {lineno}, columna {col_num}: Función '{func_name}' esperaba {len(params_def)} argumentos, pero recibió {len(args_tuplas)}.")
        p[0] = (contexto.nuevo_temporal(), 'error_args_incorrectos')
        return

    args_val_str_list = []
    for i, (arg_val, arg_tipo) in enumerate(args_tuplas):
        param_tipo_esperado, _ = params_def[i]
        if arg_tipo.startswith('error_'):
            contexto.errores.append(
                f"Error semántico en línea {lineno}, columna {col_num}: Argumento {i + 1} para '{func_name}' es inválido.")
            p[0] = (contexto.nuevo_temporal(), 'error_args_incorrectos')
            return
        if arg_tipo != param_tipo_esperado and not (param_tipo_esperado == 'float' and arg_tipo == 'int'):
            contexto.errores.append(
                f"Error semántico en línea {lineno}, columna {col_num}: Argumento {i + 1} para '{func_name}'. Se esperaba tipo '{param_tipo_esperado}', pero se obtuvo '{arg_tipo}'.")
            p[0] = (contexto.nuevo_temporal(), 'error_args_incorrectos')
            return
        args_val_str_list.append(arg_val)

    temp = contexto.nuevo_temporal()
    args_str_3ac = ", ".join(args_val_str_list) if args_val_str_list else ""
    contexto.emitir(f"{temp} = call {func_name}, [{args_str_3ac}]", f"Llamada a función {func_name} con retorno")

    tipo_retorno = func_info.get('tipo_retorno', 'void')  # Asumir void si no está definido
    if tipo_retorno == 'void':
        contexto.errores.append(
            f"Error semántico en línea {lineno}, columna {col_num}: Función '{func_name}' de tipo 'void' usada en una expresión que espera un valor.")
        tipo_retorno = 'error_void_en_expresion'  # Marcar como error

    contexto.agregar_simbolo_temporal(temp, tipo_retorno)
    p[0] = (temp, tipo_retorno)


def p_llamada_funcion_simple(p):
    """
    llamada_funcion_simple : IDENTIFICADOR PARENTESIS_IZQ argumentos PARENTESIS_DER
    """
    # Similar a p_llamada_funcion_expr pero sin asignación a temporal (ej. para funciones void)
    func_name = p[1]
    args_tuplas = p[3]
    lineno = p.lineno(1)
    col_num = encontrar_columna(analizador_lexico.lexdata, p.lexpos(1))

    func_info = contexto.funciones.get(func_name)
    if not func_info:
        contexto.errores.append(
            f"Error semántico en línea {lineno}, columna {col_num}: Función '{func_name}' no declarada.")
        p[0] = None  # Error en la sentencia
        return

    params_def = func_info['params']
    if len(args_tuplas) != len(params_def):
        contexto.errores.append(
            f"Error semántico en línea {lineno}, columna {col_num}: Función '{func_name}' esperaba {len(params_def)} argumentos, pero recibió {len(args_tuplas)}.")
        p[0] = None
        return

    args_val_str_list = []
    for i, (arg_val, arg_tipo) in enumerate(args_tuplas):
        param_tipo_esperado, _ = params_def[i]
        if arg_tipo.startswith('error_'):
            contexto.errores.append(
                f"Error semántico en línea {lineno}, columna {col_num}: Argumento {i + 1} para '{func_name}' es inválido.")
            p[0] = None
            return
        if arg_tipo != param_tipo_esperado and not (param_tipo_esperado == 'float' and arg_tipo == 'int'):
            contexto.errores.append(
                f"Error semántico en línea {lineno}, columna {col_num}: Argumento {i + 1} para '{func_name}'. Se esperaba tipo '{param_tipo_esperado}', pero se obtuvo '{arg_tipo}'.")
            p[0] = None
            return
        args_val_str_list.append(arg_val)

    args_str_3ac = ", ".join(args_val_str_list) if args_val_str_list else ""
    contexto.emitir(f"call {func_name}, [{args_str_3ac}]", f"Llamada a función {func_name} (posiblemente void)")
    p[0] = ('llamada_funcion_simple', func_name, args_val_str_list)  # Tupla informativa


def p_argumentos(p):
    """
    argumentos : expresion_lista
               |
    """
    if len(p) == 2:
        p[0] = p[1]  # p[1] es la lista de tuplas (val, tipo)
    else:
        p[0] = []  # Lista vacía si no hay argumentos


def p_expresion_lista(p):
    """
    expresion_lista : expresion
                    | expresion_lista COMA expresion
    """
    if len(p) == 2:  # expresion
        p[0] = [p[1]]  # Lista con una tupla (val, tipo)
    else:  # expresion_lista COMA expresion
        p[0] = p[1] + [p[3]]  # Añadir la nueva tupla (val, tipo) a la lista


def p_expresion_array_access(p):
    """
    expresion : IDENTIFICADOR CORCHETE_IZQ expresion CORCHETE_DER
    """
    array_name = p[1]
    idx_val_str, idx_tipo_str = p[3]
    lineno = p.lineno(1)
    col_num = encontrar_columna(analizador_lexico.lexdata, p.lexpos(1))

    simbolo_array = contexto.obtener_simbolo(array_name,
                                             func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None)
    if not simbolo_array or not simbolo_array['tipo'].startswith('array('):
        contexto.errores.append(
            f"Error semántico en línea {lineno}, columna {col_num}: '{array_name}' no es un array o no ha sido declarado.")
        p[0] = (contexto.nuevo_temporal(), 'error_no_es_array')
        return

    if idx_tipo_str != 'int':
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(3)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(3))}: El índice del array '{array_name}' debe ser un entero, se obtuvo '{idx_tipo_str}'.")
        p[0] = (contexto.nuevo_temporal(), 'error_indice_no_entero')
        return

    # Determinar tipo del elemento del array
    match_tipo_array = re.match(r'array\((\w+),', simbolo_array['tipo'])
    if not match_tipo_array:
        contexto.errores.append(
            f"Error semántico en línea {lineno}, columna {col_num}: Formato de tipo de array inválido para '{array_name}'.")
        p[0] = (contexto.nuevo_temporal(), 'error_formato_array')
        return

    tipo_elemento_array = match_tipo_array.group(1)

    temp_idx = contexto.nuevo_temporal()
    contexto.emitir(f"{temp_idx} = {idx_val_str}", f"Calcular índice para acceso a {array_name}")
    temp_val_acceso = contexto.nuevo_temporal()
    contexto.emitir(f"{temp_val_acceso} = {array_name}[{temp_idx}]", f"Acceder a elemento {array_name}[{idx_val_str}]")
    contexto.agregar_simbolo_temporal(temp_val_acceso, tipo_elemento_array)
    p[0] = (temp_val_acceso, tipo_elemento_array)


def p_declaracion_array(p):
    """
    declaracion_array : tipo_dato IDENTIFICADOR CORCHETE_IZQ NUMERO CORCHETE_DER
                      | tipo_dato IDENTIFICADOR CORCHETE_IZQ NUMERO CORCHETE_DER IGUAL LLAVE_IZQ lista_valores LLAVE_DER
    """
    tipo_base = p[1]
    array_name = p[2]
    # p[4] es el token NUMERO, su valor es int o float. Necesitamos el valor real.
    # Acceder a p.slice[4].value para el valor original del token NUMERO.
    try:
        size = int(p.slice[4].value)  # p.slice da acceso a los tokens de la regla
        if size <= 0:
            raise ValueError("El tamaño del array debe ser positivo.")
    except ValueError as e:
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(4)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(4))}: Tamaño de array inválido '{p.slice[4].value}'. {e}")
        p[0] = None
        return

    lineno = p.lineno(2)
    col_num = encontrar_columna(analizador_lexico.lexdata, p.lexpos(2))
    tipo_array_completo = f"array({tipo_base}, {size})"

    if not contexto.agregar_simbolo(array_name, tipo_array_completo, lineno, col_num,
                                    func_name=contexto.contexto_actual if contexto.contexto_actual != "global" else None):
        p[0] = None  # Error al agregar
        return

    contexto.emitir(f"declare array {tipo_base} {array_name}[{size}]",
                    f"Declarar array {array_name} de tipo {tipo_base} tamaño {size}")

    valores_iniciales_tuplas = []
    if len(p) == 10:  # Con inicialización: ... = { lista_valores }
        valores_iniciales_tuplas = p[8]  # lista de tuplas (val_str, tipo_str)
        if len(valores_iniciales_tuplas) > size:
            contexto.errores.append(
                f"Error semántico en línea {p.lineno(7)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(7))}: Demasiados inicializadores para el array '{array_name}'. Esperados {size}, recibidos {len(valores_iniciales_tuplas)}.")
            # Truncar a los primeros 'size' elementos si hay demasiados
            valores_iniciales_tuplas = valores_iniciales_tuplas[:size]

        for i, (val_str, tipo_str) in enumerate(valores_iniciales_tuplas):
            if tipo_str.startswith('error_'):
                contexto.errores.append(
                    f"Error semántico en línea {p.lineno(8)}: Valor de inicialización {i + 1} para '{array_name}' es inválido.")
                continue  # Saltar este valor

            if tipo_base != tipo_str and not (tipo_base == 'float' and tipo_str == 'int'):
                contexto.errores.append(
                    f"Error semántico en línea {p.lineno(8)}: Tipo incompatible en inicializador {i + 1} para '{array_name}'. Se esperaba '{tipo_base}', se obtuvo '{tipo_str}'.")
                continue

            temp_init_val = contexto.nuevo_temporal()
            contexto.emitir(f"{temp_init_val} = {val_str}", f"Valor de inicialización para {array_name}[{i}]")
            contexto.emitir(f"{array_name}[{i}] = {temp_init_val}", f"Inicializar {array_name}[{i}]")

    p[0] = ('declaracion_array', array_name, tipo_base, size, valores_iniciales_tuplas)


def p_lista_valores(p):
    """
    lista_valores : expresion
                  | lista_valores COMA expresion
    """
    # Esta regla se usa para argumentos de función y para inicializadores de array.
    # Debe devolver una lista de tuplas (valor_str, tipo_str).
    if len(p) == 2:  # expresion
        p[0] = [p[1]]  # p[1] ya es (val, tipo)
    else:  # lista_valores COMA expresion
        p[0] = p[1] + [p[3]]  # p[1] es lista de (val,tipo), p[3] es (val,tipo)


def p_bloque(p):
    """
    bloque : LLAVE_IZQ NEWLINE sentencias_opt NEWLINE LLAVE_DER
           | LLAVE_IZQ NEWLINE sentencias_opt LLAVE_DER
           | LLAVE_IZQ sentencias_opt NEWLINE LLAVE_DER
           | LLAVE_IZQ sentencias_opt LLAVE_DER
    """
    if len(p) == 6:
        p[0] = p[3]  # Tiene NEWLINE antes y después
    elif len(p) == 5:
        if isinstance(p[2], list):
            p[0] = p[2]  # Tiene sentencias_opt en la segunda posición
        else:
            p[0] = p[3]  # Tiene NEWLINE al inicio, sentencias_opt en 3ra pos
    else:
        p[0] = p[2]  # Solo sentencias_opt sin NEWLINE explícito


def p_condicion(p):
    """
    condicion : SI PARENTESIS_IZQ expresion PARENTESIS_DER bloque
              | SI PARENTESIS_IZQ expresion PARENTESIS_DER bloque SINO bloque
    """
    cond_val_str, cond_tipo_str = p[3]
    lineno_if = p.lineno(1)

    if cond_tipo_str.startswith('error_'):
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(3)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(3))}: Condición de 'si' inválida.")
        p[0] = None  # Error en la sentencia 'si'
        return
    if cond_tipo_str != 'bool':
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(3)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(3))}: Condición de 'si' debe ser booleana, no '{cond_tipo_str}'.")
        # Se podría intentar continuar asumiendo que se evaluará a true/false, pero es mejor marcar error.

    label_else = contexto.nueva_etiqueta()
    label_fin_si = contexto.nueva_etiqueta()

    contexto.emitir(f"if not {cond_val_str} goto {label_else}", f"Condición SI (línea {lineno_if})")

    # Bloque SI (p[5] es la lista de tuplas de sentencia)
    if p[5]:
        for stmt_tuple in p[5]:
            contexto.emitir(stmt_tuple)  # Emitir cada sentencia del bloque

    if len(p) == 8:  # Hay bloque SINO
        contexto.emitir(f"goto {label_fin_si}", "Saltar bloque SINO")
        contexto.emitir(f"{label_else}:", "Etiqueta SINO")
        # Bloque SINO (p[7])
        if p[7]:
            for stmt_tuple in p[7]:
                contexto.emitir(stmt_tuple)
        contexto.emitir(f"{label_fin_si}:", "Fin de SI-SINO")
    else:  # Solo SI
        contexto.emitir(f"{label_else}:", "Fin de SI (etiqueta para salto si falso)")

    p[0] = ('condicion', (cond_val_str, cond_tipo_str), p[5], p[7] if len(p) == 8 else None)


def p_mientras(p):
    """
    mientras : MIENTRAS PARENTESIS_IZQ expresion PARENTESIS_DER bloque
    """
    cond_val_str, cond_tipo_str = p[3]
    bloque_stmts_tuples = p[5]
    lineno_mientras = p.lineno(1)

    if cond_tipo_str.startswith('error_'):
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(3)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(3))}: Condición de 'mientras' inválida.")
        p[0] = None
        return
    if cond_tipo_str != 'bool':
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(3)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(3))}: Condición de 'mientras' debe ser booleana, no '{cond_tipo_str}'.")

    label_inicio_mientras = contexto.nueva_etiqueta()
    label_fin_mientras = contexto.nueva_etiqueta()

    contexto.emitir(f"{label_inicio_mientras}:", f"Inicio bucle MIENTRAS (línea {lineno_mientras})")
    contexto.emitir(f"if not {cond_val_str} goto {label_fin_mientras}", "Condición MIENTRAS")

    if bloque_stmts_tuples:
        for stmt_tuple in bloque_stmts_tuples:
            contexto.emitir(stmt_tuple)

    contexto.emitir(f"goto {label_inicio_mientras}", "Volver a evaluar condición MIENTRAS")
    contexto.emitir(f"{label_fin_mientras}:", "Fin bucle MIENTRAS")
    p[0] = ('mientras', (cond_val_str, cond_tipo_str), bloque_stmts_tuples)


def p_para(p):
    """
    para : PARA PARENTESIS_IZQ asignacion_opt PUNTO_COMA expresion PUNTO_COMA asignacion_opt PARENTESIS_DER bloque
    """
    init_stmt_tuple = p[3]
    cond_expr_val_str, cond_expr_tipo_str = p[5]
    incr_stmt_tuple = p[7]
    loop_body_stmts_tuples = p[9]
    lineno_para = p.lineno(1)

    if cond_expr_tipo_str.startswith('error_'):
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(5)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(5))}: Condición de 'para' inválida.")
        p[0] = None
        return
    if cond_expr_tipo_str != 'bool':
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(5)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(5))}: Condición de 'para' debe ser booleana, no '{cond_expr_tipo_str}'.")

    label_cond_para = contexto.nueva_etiqueta()
    label_incr_para = contexto.nueva_etiqueta()
    label_fin_para = contexto.nueva_etiqueta()

    contexto.emitir(f"# Inicio bucle PARA (línea {lineno_para})")
    if init_stmt_tuple:
        print("[DEBUG] init_stmt_tuple:", init_stmt_tuple)
        contexto.emitir(init_stmt_tuple)

    contexto.emitir(f"{label_cond_para}:", "Etiqueta condición PARA")
    contexto.emitir(f"if not {cond_expr_val_str} goto {label_fin_para}", "Condición PARA")

    if loop_body_stmts_tuples:
        for stmt_tuple in loop_body_stmts_tuples:
            contexto.emitir(stmt_tuple)

    contexto.emitir(f"{label_incr_para}:", "Etiqueta incremento PARA")
    if incr_stmt_tuple:
        print("[DEBUG] incr_stmt_tuple:", incr_stmt_tuple)
        contexto.emitir(incr_stmt_tuple)

    contexto.emitir(f"goto {label_cond_para}", "Volver a evaluar condición PARA")
    contexto.emitir(f"{label_fin_para}:", "Fin bucle PARA")

    p[0] = ('para', init_stmt_tuple, (cond_expr_val_str, cond_expr_tipo_str), incr_stmt_tuple, loop_body_stmts_tuples)


def p_asignacion_opt(p):
    """
    asignacion_opt : asignacion
                   |
    """
    if len(p) == 2:
        p[0] = p[1]  # p[1] es la tupla de info de 'asignacion'
    else:
        p[0] = None


def p_retornar(p):
    """
    retornar : RETORNAR expresion
    """
    # Validar que estamos dentro de una función
    if contexto.contexto_actual == "global":
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(1)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(1))}: Sentencia 'retornar' fuera de una función.")
        p[0] = None
        return

    expr_val_str, expr_tipo_str = p[2]
    if expr_tipo_str.startswith('error_'):
        contexto.errores.append(
            f"Error semántico en línea {p.lineno(2)}, columna {encontrar_columna(analizador_lexico.lexdata, p.lexpos(2))}: Expresión de retorno inválida.")
        p[0] = None
        return

    # Validar tipo de retorno con la definición de la función
    current_func_info = contexto.funciones.get(contexto.contexto_actual)
    if current_func_info:
        tipo_retorno_esperado = current_func_info['tipo_retorno']
        if tipo_retorno_esperado == 'void' and expr_tipo_str != 'void_placeholder':  # void_placeholder para return;
            contexto.errores.append(
                f"Error semántico en línea {p.lineno(1)}: Función '{contexto.contexto_actual}' es void, no debe retornar un valor.")
        elif tipo_retorno_esperado != expr_tipo_str and not (
                tipo_retorno_esperado == 'float' and expr_tipo_str == 'int'):
            contexto.errores.append(
                f"Error semántico en línea {p.lineno(1)}: Tipo de retorno incompatible para '{contexto.contexto_actual}'. Se esperaba '{tipo_retorno_esperado}', se obtuvo '{expr_tipo_str}'.")

    contexto.emitir(f"RETURN {expr_val_str}",
                    f"Retornar valor (tipo {expr_tipo_str}) de función {contexto.contexto_actual}")
    p[0] = ('retornar', expr_val_str, expr_tipo_str)


# Podríamos tener una regla para 'RETORNAR' sin expresión para funciones void, si se desea.
# retornar : RETORNAR  (esto necesitaría que expresion sea opcional o una nueva regla)

def p_declaracion_funcion(p):
    """
    declaracion_funcion : FUNC IDENTIFICADOR PARENTESIS_IZQ parametros PARENTESIS_DER bloque
                        | FUNC tipo_dato IDENTIFICADOR PARENTESIS_IZQ parametros PARENTESIS_DER bloque
    """
    # FUNC tipo_ret ID ( params ) bloque  (len=8)
    # FUNC ID ( params ) bloque (len=7, tipo_retorno es void por defecto)

    idx_nombre_func = 2
    idx_params = 4
    idx_bloque = 6
    tipo_retorno = 'void'  # Por defecto si no se especifica

    if p.slice[2].type == 'tipo_dato':  # FUNC tipo_ret ID ...
        tipo_retorno = p[2]
        idx_nombre_func = 3
        idx_params = 5
        idx_bloque = 7

    func_name = p[idx_nombre_func]
    params_tuplas = p[idx_params]  # Lista de (tipo_str, nombre_param_str)
    func_body_stmts_tuples = p[idx_bloque]
    lineno_func = p.lineno(1)
    col_num_func = encontrar_columna(analizador_lexico.lexdata, p.lexpos(1))

    if not contexto.registrar_funcion(func_name, tipo_retorno, params_tuplas, lineno_func, col_num_func):
        p[0] = None  # Error al registrar
        return

    # Guardar contexto anterior y establecer el nuevo para la función
    contexto_anterior = contexto.contexto_actual
    contexto.contexto_actual = func_name

    contexto.emitir(f"FUNC {func_name}:",
                    f"Definición función {func_name} (retorna {tipo_retorno}, línea {lineno_func})")

    # Agregar parámetros al scope de la función (tabla de símbolos)
    for param_tipo, param_name in params_tuplas:
        # Los parámetros ya se deberían agregar en p_parametros si queremos que estén disponibles
        # inmediatamente para chequeo de duplicados dentro de la lista de parámetros.
        # Aquí, es más para asegurar que el scope esté bien.
        # Si p_parametros ya los agregó, esto podría dar error de redeclaración si no se maneja.
        # Se modifica agregar_simbolo para manejar el contexto actual.
        # Necesitamos lineno/col para el parámetro si se declara aquí. Usamos la de la función.
        if not contexto.agregar_simbolo(param_name, param_tipo, lineno_func, col_num_func, es_param=True,
                                        func_name=func_name):
            # Error de redeclaración de parámetro (o con otro símbolo en el scope de la func)
            # El error ya se añadió en agregar_simbolo.
            pass

    if func_body_stmts_tuples:
        for stmt_tuple in func_body_stmts_tuples:
            contexto.emitir(stmt_tuple)

    contexto.emitir(f"END_FUNC {func_name}", f"Fin de función {func_name}")

    # Restaurar contexto anterior
    contexto.contexto_actual = contexto_anterior
    p[0] = ('declaracion_funcion', func_name, tipo_retorno, params_tuplas, func_body_stmts_tuples)


def p_parametros(p):
    """
    parametros : lista_parametros
               |
    """
    if len(p) == 2:
        p[0] = p[1]  # Lista de tuplas (tipo, nombre)
    else:
        p[0] = []


def p_lista_parametros(p):
    """
    lista_parametros : tipo_dato IDENTIFICADOR
                     | lista_parametros COMA tipo_dato IDENTIFICADOR
    """
    if len(p) == 3:  # tipo_dato IDENTIFICADOR
        tipo_param = p[1]
        nombre_param = p[2]
        # Validar aquí si el nombre del parámetro ya fue usado en esta misma lista de parámetros
        # Esto requiere pasar la lista acumulada o chequearla.
        # Por ahora, el chequeo principal de duplicados será en agregar_simbolo dentro de la función.
        p[0] = [(tipo_param, nombre_param)]
        # No agregar a la tabla de símbolos aquí, se hará en p_declaracion_funcion
        # para que el scope (nombre de la función) sea correcto.
    else:  # lista_parametros COMA tipo_dato IDENTIFICADOR
        tipo_param = p[3]
        nombre_param = p[4]
        # Chequear si nombre_param ya está en p[1] (lista de params anteriores)
        for _, prev_name in p[1]:
            if prev_name == nombre_param:
                lineno = p.lineno(4)
                col = encontrar_columna(analizador_lexico.lexdata, p.lexpos(4))
                contexto.errores.append(
                    f"Error semántico en línea {lineno}, columna {col}: Nombre de parámetro '{nombre_param}' duplicado en la definición de función.")
                # Devolver la lista sin el duplicado o marcar error general
                # p[0] = p[1] # Omitir el duplicado
                # Para simplicidad, podemos permitir que pase y el error de agregar_simbolo lo capture,
                # o mejor, manejarlo explícitamente.
                # Si queremos ser estrictos:
                # raise SyntaxError(...) # Esto detendría el parser, no ideal.
                # Continuar y dejar que agregar_simbolo lo detecte.
                break  # Sale del for, el parámetro se añadirá y luego dará error de duplicado.

        p[0] = p[1] + [(tipo_param, nombre_param)]


# --- Manejo de Errores de Sintaxis ---
def p_error(p):
    if p:
        line_num = p.lineno
        # p.lexpos es la posición del token de error.
        # lexer.lexdata es el input completo, necesario para encontrar_columna.
        col_num = encontrar_columna(analizador_lexico.lexdata, p.lexpos)
        error_msg = f"Error de sintaxis en línea {line_num}, columna {col_num}: Token inesperado '{p.value}' (tipo: {p.type})"
        contexto.errores.append(error_msg)
        print(error_msg)
        # Se podría intentar recuperación de errores aquí, pero es complejo.
        # Por ahora, se detiene en el primer error de sintaxis o sigue si PLY puede.
    else:
        # Esto usualmente significa EOF inesperado.
        # Si lexer.lexpos está disponible, podemos intentar obtener la última línea.
        # last_line = analizador_lexico.lineno
        error_msg = "Error de sintaxis: Fin de archivo inesperado."
        contexto.errores.append(error_msg)
        print(error_msg)


# Construir el parser
parser = yacc.yacc(debug=True, optimize=False)  # debug=True es útil para desarrollo


def analizar_codigo(codigo_fuente):
    contexto.reset()
    errores_lexicos_globales.clear()  # Limpiar de ejecuciones anteriores

    print("\n=== INICIANDO ANÁLISIS ===")

    # --- Paso 1: Análisis Léxico y Captura de Tokens ---
    analizador_lexico.input(codigo_fuente)
    todos_los_tokens = []
    print("\n[TOKENS RECONOCIDOS]")
    while True:
        tok = analizador_lexico.token()
        if not tok:
            break
        todos_los_tokens.append(tok)
        col = encontrar_columna(codigo_fuente, tok.lexpos)
        print(f"Línea {tok.lineno}, Col {col}: {tok.type}({tok.value})")

    # Combinar errores léxicos detectados por t_error con los del contexto
    contexto.errores.extend(errores_lexicos_globales)

    # --- Paso 2: Parsing y Análisis Semántico (integrado en reglas) ---
    # Resetear el lexer para el parser (aunque ya se consumieron tokens, yacc lo maneja si se pasa lexer)
    # Es mejor que el parser use una instancia fresca del lexer o que el lexer se reinicie
    analizador_lexico.input(codigo_fuente)  # Reiniciar el lexer para el parser

    print("\n[INICIANDO PARSER Y ANÁLISIS SEMÁNTICO]")
    if not errores_lexicos_globales:  # Solo parsear si no hay errores léxicos fatales
        try:
            parser.parse(codigo_fuente, lexer=analizador_lexico)
        except lex.LexError as e:  # Capturar errores léxicos que puedan surgir durante el parseo (raro si ya se escaneó)
            error_msg = f"Error léxico durante el parseo: {e}"
            contexto.errores.append(error_msg)
            print(error_msg)
        except Exception as e:
            error_msg = f"Error inesperado durante el parsing: {e}"
            contexto.errores.append(error_msg)
            print(error_msg)  # Stack trace puede ser útil aquí
            import traceback
            traceback.print_exc()

    # --- Paso 3: Generación de Código y Reporte ---
    if contexto.errores:
        print("\n[ERRORES IMPIDIERON GENERACIÓN COMPLETA DE CÓDIGO]")
        for error in contexto.errores:
            print(error)
        # Generar bitácora incluso con errores
        generar_bitacora_html(
            "bitacora_compilacion.html",
            codigo_fuente,
            todos_los_tokens,
            contexto.errores,  # Ya incluye errores léxicos
            [],  # Sin código optimizado
            "",  # Sin código C++
            contexto.tabla_simbolos
        )
        return None, None, None, contexto.errores
    else:
        print("\n[ANÁLISIS COMPLETO Y SIN ERRORES SEMÁNTICOS/SINTÁCTICOS]")

        print("\n[CÓDIGO DE TRES DIRECCIONES GENERADO]")
        for line in contexto.codigo_tres_direcciones:
            print(line)

        contexto.optimizar_codigo()
        print("\n[CÓDIGO DE TRES DIRECCIONES OPTIMIZADO]")
        if contexto.codigo_optimizado:
            for line in contexto.codigo_optimizado:
                print(line)
        else:
            print("(No se aplicaron optimizaciones o el código optimizado es el mismo que el original)")

        contexto.generar_cpp()
        print("\n[CÓDIGO C++ GENERADO]")
        print(contexto.codigo_cpp)

        generar_bitacora_html(
            "bitacora_compilacion.html",
            codigo_fuente,
            todos_los_tokens,
            contexto.errores,  # Debería estar vacía si llegamos aquí
            contexto.codigo_optimizado if contexto.codigo_optimizado else contexto.codigo_tres_direcciones,
            contexto.codigo_cpp,
            contexto.tabla_simbolos
        )
        return contexto.codigo_tres_direcciones, contexto.codigo_optimizado, contexto.codigo_cpp, contexto.errores


def seleccionar_y_analizar_archivo():
    file_path = filedialog.askopenfilename(
        title="Seleccionar archivo de código fuente",
        filetypes=[("Archivos de texto", "*.txt"), ("Todos los archivos", "*.*")]
    )
    if file_path:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                codigo_fuente = file.read()
            print(f"--- Analizando archivo: {file_path} ---")
            analizar_codigo(codigo_fuente)
            print(f"--- Análisis de {file_path} finalizado ---")
        except FileNotFoundError:
            print(f"Error: Archivo '{file_path}' no encontrado.")
        except Exception as e:
            print(f"Ocurrió un error al leer o analizar el archivo: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    # Opción 1: Probar con un archivo específico (descomentar para usar)
    # test_code_path = "Codigos Prueba Desordenados.txt"
    # print(f"--- Analizando archivo de prueba: {test_code_path} ---")
    # try:
    #     with open(test_code_path, 'r', encoding='utf-8') as f:
    #         test_code = f.read()
    #     analizar_codigo(test_code)
    # except FileNotFoundError:
    #     print(f"Error: Archivo '{test_code_path}' no encontrado.")
    # except Exception as e:
    #     print(f"Ocurrió un error al leer el archivo de prueba: {e}")
    #     import traceback
    #     traceback.print_exc()
    # print(f"--- Análisis de prueba finalizado ---")

    # Opción 2: Usar GUI para seleccionar archivo
    try:
        root = tk.Tk()
        root.withdraw()  # Ocultar la ventana principal de Tk
        seleccionar_y_analizar_archivo()
    except Exception as e:
        print(f"Error con la interfaz gráfica o durante el análisis: {e}")
    finally:
        if 'root' in locals() and root:
            try:
                root.destroy()
            except tk.TclError:
                pass  # Ventana ya podría estar destruida