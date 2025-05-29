import tkinter as tk
from tkinter import filedialog
import ply.lex as lex

tokens = [
    'INT_TYPE',
    'FLOAT_TYPE',
    'STRING_TYPE',
    'BOOL_TYPE',
    'BOOLEANO',
    # Operadores
    'NEWLINE', 'MAS', 'MENOS', 'MULT', 'DIV', 'MOD',
    'IGUAL', 'MAYOR', 'MENOR', 'MAYOR_IGUAL', 'MENOR_IGUAL',
    'IGUAL_IGUAL', 'DIFERENTE',

    # Lógicos
    'Y', 'O', 'NO',

    # Delimitadores
    'PARENTESIS_IZQ', 'PARENTESIS_DER',
    'CORCHETE_IZQ', 'CORCHETE_DER',
    'LLAVE_IZQ', 'LLAVE_DER',
    'COMA', 'PUNTO_COMA',

    # Identificadores y literales
    'IDENTIFICADOR', 'NUMERO', 'CADENA'
]


def t_INT_TYPE(t):
    r'int'
    return t


def t_FLOAT_TYPE(t):
    r'float'
    return t


def t_STRING_TYPE(t):
    r'string'
    return t


def t_BOOLEANO(t):
    r'true|false'
    # Asegurar que el valor sea booleano en Python para consistencia si se usa en el parser
    # t.value = True if t.value == 'true' else False # Opcional, si quieres el valor Python bool
    return t


def t_BOOL_TYPE(t):
    r'bool'
    return t


# Palabras reservadas
reservadas = {
    'imprimir': 'IMPRIMIR',
    'si': 'SI',
    'sino': 'SINO',
    'para': 'PARA',
    'mientras': 'MIENTRAS',
    'func': 'FUNC',
    'retornar': 'RETORNAR',
    'leer': 'LEER',
    'rango': 'RANGO'  # RANGO no está usado en la gramática del parser, pero se mantiene
}

tokens += list(reservadas.values())

# Expresiones regulares para tokens simples
t_ignore = ' \t'
t_MAS = r'\+'
t_MENOS = r'-'
t_MULT = r'\*'
t_DIV = r'/'
t_MOD = r'%'
t_IGUAL = r'='
t_MAYOR = r'>'
t_MENOR = r'<'
t_MAYOR_IGUAL = r'>='
t_MENOR_IGUAL = r'<='
t_IGUAL_IGUAL = r'=='
t_DIFERENTE = r'!='
t_Y = r'\by\b'  # Usar \b para asegurar que 'y' sea una palabra completa
t_O = r'\bo\b'  # Usar \b para asegurar que 'o' sea una palabra completa
t_NO = r'\bno\b'  # Usar \b para asegurar que 'no' sea una palabra completa
t_PARENTESIS_IZQ = r'\('
t_PARENTESIS_DER = r'\)'
t_CORCHETE_IZQ = r'\['
t_CORCHETE_DER = r'\]'
t_LLAVE_IZQ = r'\{'
t_LLAVE_DER = r'\}'
t_COMA = r','
t_PUNTO_COMA = r';'  # PUNTO_COMA no está usado en la gramática del parser, pero se mantiene


def t_COMENTARIO(t):
    r'\#.*\n'
    t.lexer.lineno += 1
    pass  # Ignorar comentarios


def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    t.type = 'NEWLINE'
    # Retornar NEWLINE ya que es usado por la gramática
    return t


def t_IDENTIFICADOR(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reservadas.get(t.value, 'IDENTIFICADOR')
    return t


def t_NUMERO(t):
    r'\d+(\.\d+)?'
    # El parser espera strings para los literales en p[0] de expresiones,
    # la conversión a float/int se hace para el valor del token, pero el parser usará str(p[1])
    if '.' in t.value:
        t.value = float(t.value)
    else:
        t.value = int(t.value)
    return t


def t_CADENA(t):
    r'"(?:\\"|[^"])*"'
    t.value = t.value[1:-1].replace('\\"', '"')  # Remover comillas y escapar comillas internas
    return t


errores_lexicos = []


def encontrar_columna(input_data, token_lexpos):
    if input_data is None or token_lexpos is None:
        return 0
    last_newline = input_data.rfind('\n', 0, token_lexpos)
    if last_newline == -1:
        return token_lexpos + 1
    else:
        return (token_lexpos - last_newline)


def t_error(t):
    col = encontrar_columna(t.lexer.lexdata, t.lexpos)
    error_msg = f"Error léxico en línea {t.lineno}, columna {col}: Carácter ilegal o inesperado '{t.value[0]}'"
    errores_lexicos.append(error_msg)
    t.lexer.skip(1)


lexer = lex.lex()


def generar_bitacora_html(file_path, codigo_fuente, tokens_list, errores_list, codigo_optimizado, codigo_cpp,
                          symbol_table=None):
    """
    Generates an HTML report (bitácora) of the compilation process.
    """
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html>\n")
        f.write("<html>\n")
        f.write("<head>\n")
        f.write("    <title>Bitácora de Compilación</title>\n")
        f.write("    <style>\n")
        f.write(
            "        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f4f4f4; color: #333; }\n")
        f.write("        h1 { text-align: center; color: #333; }\n")
        f.write(
            "        h2 { color: #0056b3; border-bottom: 2px solid #0056b3; padding-bottom: 5px; margin-top: 30px; }\n")
        f.write(
            "        table { width: 100%; border-collapse: collapse; margin-bottom: 20px; background-color: #fff; box-shadow: 0 0 10px rgba(0, 0, 0, 0.1); }\n")
        f.write("        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }\n")
        f.write("        th { background-color: #e2e2e2; }\n")
        f.write("        ul { list-style-type: none; padding: 0; }\n")
        f.write(
            "        li.error-item { background-color: #ffe6e6; border-left: 5px solid #ff4d4d; margin-bottom: 5px; padding: 8px; }\n")
        f.write(
            "        pre { background-color: #eee; padding: 10px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; word-wrap: break-word; }\n")
        f.write(
            "        .success { background-color: #e6ffe6; border-left: 5px solid #4dff4d; padding: 10px; margin-bottom: 10px; }\n")
        f.write("        .code-block { margin-bottom: 20px; }\n")
        f.write("    </style>\n")
        f.write("</head>\n")
        f.write("<body>\n")

        f.write("<h1>Informe de Compilación</h1>\n")

        # --- Tokens Section ---
        f.write("<h2>Lista de Tokens</h2>\n")
        if tokens_list:
            f.write("<table border='1'><tr><th>Tipo</th><th>Valor</th><th>Línea</th><th>Columna</th></tr>\n")
            for token in tokens_list:
                col = encontrar_columna(codigo_fuente, token.lexpos)
                f.write(
                    f"<tr><td>{token.type}</td><td>{str(token.value)}</td><td>{token.lineno}</td><td>{col}</td></tr>\n")
            f.write("</table>\n")
        else:
            f.write("<p>No se generaron tokens o la lista de tokens está vacía.</p>\n")

        # --- Errors Section ---
        f.write("<h2>Errores y Advertencias</h2>\n")
        if errores_list:
            f.write("<ul>\n")
            for error in errores_list:
                f.write(f"<li class='error-item'>{error}</li>\n")
            f.write("</ul>\n")
        else:
            f.write("<p class='success'>No se encontraron errores léxicos, sintácticos o semánticos.</p>\n")

        # --- Symbol Table Section ---
        f.write("<h2>Tabla de Símbolos</h2>\n")
        if symbol_table:
            f.write("<table border='1'><tr><th>Nombre</th><th>Tipo</th><th>Valor</th><th>Ámbito</th></tr>\n")
            for name, details in symbol_table.items():
                valor_str = str(details.get('valor', 'N/A'))
                # Truncate long values for display if necessary
                if len(valor_str) > 50:
                    valor_str = valor_str[:47] + "..."
                f.write(
                    f"<tr><td>{name}</td><td>{details.get('tipo', 'N/A')}</td><td>{valor_str}</td><td>{details.get('scope', 'global')}</td></tr>\n")
            f.write("</table>\n")
        else:
            f.write("<p>Tabla de símbolos no disponible o vacía.</p>\n")

        # --- Optimized 3-Address Code Section ---
        f.write("<div class='code-block'>\n")
        f.write("<h2>Código de Tres Direcciones Optimizado</h2>\n")
        if codigo_optimizado:
            f.write("<pre>\n")
            for linea in codigo_optimizado:
                f.write(f"{linea}\n")
            f.write("</pre>\n")
        else:
            f.write("<p>No se generó código de tres direcciones optimizado (o hubo errores previos).</p>\n")
        f.write("</div>\n")

        # --- C++ Code Section ---
        f.write("<div class='code-block'>\n")
        f.write("<h2>Código C++ Generado</h2>\n")
        if codigo_cpp:
            f.write("<pre>\n")
            f.write(codigo_cpp)  # codigo_cpp ya es un string
            f.write("</pre>\n")
        else:
            f.write("<p>No se generó código C++ (o hubo errores previos).</p>\n")
        f.write("</div>\n")

        f.write("</body>\n")
        f.write("</html>")

    print(f"Bitácora de compilación generada: {file_path}")


def probar_lexer(codigo):
    global errores_lexicos
    errores_lexicos.clear()  # Limpiar errores de ejecuciones previas
    lexer.input(codigo)
    tokens_encontrados = []
    print("\n[TOKENS RECONOCIDOS EN PRUEBA DE LEXER]")
    while True:
        tok = lexer.token()
        if not tok:
            break
        tokens_encontrados.append(tok)
        col = encontrar_columna(codigo, tok.lexpos)
        print(f"Línea {tok.lineno}, Col {col}: {tok.type}({tok.value})")

    if errores_lexicos:
        print("\n[ERRORES LÉXICOS ENCONTRADOS EN PRUEBA]")
        for err in errores_lexicos:
            print(err)
    return tokens_encontrados, errores_lexicos


if __name__ == '__main__':
    # Ejemplo de uso para probar el lexer directamente
    test_code = """
    int x = 10;
    float y = 20.5;
    string saludo = "Hola Mundo!"; # Esto es un comentario
    bool flag = true;

    si (x > 5) {
        imprimir(saludo);
    } sino {
        imprimir("x no es mayor a 5");
    }

    # Error léxico:
    $esto_es_un_error
    """
    print("Probando el lexer...")
    tokens_res, errores_lex_res = probar_lexer(test_code)

    # Generar una bitácora de prueba solo con la info del lexer
    # Para esto, el código fuente completo es útil.
    # generar_bitacora_html("bitacora_lexer_test.html", test_code, tokens_res, errores_lex_res, [], "", {})
    print("\nPrueba del lexer finalizada.")