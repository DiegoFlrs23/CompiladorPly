from typing import ReadOnly
from urllib.request import OpenerDirector

import ply.yacc as yacc
from Lexer_Ply import tokens, errores, generar_bitacora_html
import tkinter as tk
from tkinter import filedialog
import ply.lex as lex
from Lexer_Ply import lexer

# Tabla de símbolos
tabla_simbolos = {}

# Estructura para el código de tres direcciones
codigo_tres_direcciones = []
temporal_counter = 0


def nuevo_temporal():
    global temporal_counter
    temporal_counter += 1
    return f"t{temporal_counter}"


def emitir(codigo):
    codigo_tres_direcciones.append(codigo)


# Reglas de la gramática
def p_programa(p):
    """programa : sentencias"""
    p[0] = p[1]
    # Al final del programa, imprimir el código generado
    print("\nCódigo de tres direcciones generado:")
    for instruccion in codigo_tres_direcciones:
        print(instruccion)


def p_sentencias(p):
    """sentencias : sentencia sentencias
                  | sentencia"""
    if len(p) == 3:
        p[0] = p[1] + p[2]
    else:
        p[0] = p[1]


def p_sentencia(p):
    """sentencia : asignacion
                 | imprimir
                 | condicion"""
    p[0] = p[1]


# Reglas de asignación
def p_asignacion(p):
    """asignacion : IDENTIFICADOR IGUAL expresion"""
    tabla_simbolos[p[1]] = p[3]
    if isinstance(p[3], tuple) and p[3][0] == 'temp':
        emitir(f"{p[1]} = {p[3][1]}")
    else:
        emitir(f"{p[1]} = {p[3]}")
    p[0] = (p[1], p[3])


# Reglas de expresiones
def p_expresion_binaria(p):
    """expresion : expresion MAS expresion
                 | expresion MENOS expresion
                 | expresion MULT expresion
                 | expresion DIV expresion"""
    temp = nuevo_temporal()
    operador = p[2]

    # Obtener los valores de los operandos
    op1 = p[1][1] if isinstance(p[1], tuple) and p[1][0] == 'temp' else p[1]
    op2 = p[3][1] if isinstance(p[3], tuple) and p[3][0] == 'temp' else p[3]

    emitir(f"{temp} = {op1} {operador} {op2}")
    p[0] = ('temp', temp)


def p_expresion_numero(p):
    """expresion : NUMERO"""
    p[0] = p[1]


def p_expresion_identificador(p):
    """expresion : IDENTIFICADOR"""
    p[0] = p[1]


def p_imprimir(p):
    """imprimir : IMPRIMIR PARENTESIS_IZQ CADENA PARENTESIS_DER"""
    emitir(f'imprimir "{p[3]}"')
    p[0] = p[3]


# Reglas para condicionales
def p_condicion(p):
    """condicion : SI PARENTESIS_IZQ expresion comparador expresion PARENTESIS_DER bloque"""
    temp1 = nuevo_temporal()
    temp2 = nuevo_temporal()

    # Obtener los valores de las expresiones
    op1 = p[3][1] if isinstance(p[3], tuple) and p[3][0] == 'temp' else p[3]
    op2 = p[5][1] if isinstance(p[5], tuple) and p[5][0] == 'temp' else p[5]

    comparador = p[4]
    label = nuevo_temporal().replace('t', 'L')  # Etiqueta para el salto

    emitir(f"{temp1} = {op1} {comparador} {op2}")
    emitir(f"if {temp1} goto {label}")
    emitir(f"goto {label}_end")
    emitir(f"{label}:")
    # Código del bloque
    p[0] = p[7]
    emitir(f"{label}_end:")


def p_comparador(p):
    """comparador : MAYOR
                  | MENOR
                  | MAYOR_IGUAL
                  | MENOR_IGUAL
                  | IGUAL_IGUAL
                  | DIFERENTE"""
    p[0] = p[1]


def p_bloque(p):
    """bloque : LLAVE_IZQ sentencias LLAVE_DER"""
    p[0] = p[2]


# Manejo de errores sintácticos
def p_error(p):
    if p:
        error_msg = f"[SINTACTICO] Error en linea {p.lineno}: Token inesperado '{p.value}'"
    else:
        error_msg = "[SINTACTICO] Error: Fin de archivo inesperado"
    print(error_msg)
    errores.append(error_msg)


# Construcción del parser
parser = yacc.yacc()


def obtener_tokens(codigo):
    lexer.input(codigo)
    tokens_lista = []
    while True:
        tok = lexer.token()
        if not tok:
            break
        tokens_lista.append(tok)
    return tokens_lista


def probar_parser(codigo):
    global codigo_tres_direcciones, temporal_counter
    # Reiniciar el generador de código
    codigo_tres_direcciones = []
    temporal_counter = 0

    # Obtener tokens antes de analizar el código
    tokens_lista = obtener_tokens(codigo)

    # Analizar el código con el parser
    resultado = parser.parse(codigo)

    # Generar bitácoras de errores y tabla de símbolos
    generar_bitacora_html(tokens_lista, errores, "bitacora_errores.html")

    # Imprimir errores si existen
    if errores:
        for error in errores:
            print("Error sintáctico detectado:", error)


def leer_archivo(archivo):
    try:
        with open(archivo, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: El archivo '{archivo}' no se encuentra.")
        return ""
    except Exception as e:
        print(f"Error al leer el archivo: {e}")
        return ""


def seleccionar_archivo():
    root = tk.Tk()
    root.withdraw()
    archivo = filedialog.askopenfilename(
        title="Seleccionar archivo de código",
        filetypes=[("Archivos de texto", "*.txt")]
    )
    return archivo


def main():
    ruta_archivo = seleccionar_archivo()
    if ruta_archivo:
        codigo_leido = leer_archivo(ruta_archivo)
        probar_parser(codigo_leido)
    else:
        print("No se seleccionó ningún archivo.")


if __name__ == "__main__":
    main()