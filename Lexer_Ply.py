import ply.lex as lex
import tkinter as tk
from tkinter import filedialog

# Definimos los tokens del lenguaje
tokens = (
    'IDENTIFICADOR', 'NUMERO', 'CADENA',
    'MAS', 'MENOS', 'MULT', 'DIV', 'MOD',
    'IGUAL', 'MAYOR', 'MENOR', 'MAYOR_IGUAL', 'MENOR_IGUAL', 'IGUAL_IGUAL', 'DIFERENTE',
    'Y', 'O', 'NO',
    'PARENTESIS_IZQ', 'PARENTESIS_DER', 'CORCHETE_IZQ', 'CORCHETE_DER', 'LLAVE_IZQ', 'LLAVE_DER',
    'COMA'
)

# Palabras clave del lenguaje
reservadas = {
    'imprimir': 'IMPRIMIR',
    'si': 'SI', 'sino': 'SINO',
    'para': 'PARA', 'mientras': 'MIENTRAS',
    'func': 'FUNC', 'retornar': 'RETORNAR',
    'leer': 'LEER', 'rango': 'RANGO'
}

tokens = list(tokens) + list(reservadas.values())

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
t_Y = r'y'
t_O = r'o'
t_NO = r'no'
t_PARENTESIS_IZQ = r'\('
t_PARENTESIS_DER = r'\)'
t_CORCHETE_IZQ = r'\['
t_CORCHETE_DER = r'\]'
t_LLAVE_IZQ = r'\{'
t_LLAVE_DER = r'\}'
t_COMA = r','

# Funciones para tokens
def t_IDENTIFICADOR(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reservadas.get(t.value, 'IDENTIFICADOR')
    return t

def t_NUMERO(t):
    r'\d+(\.\d+)?'
    t.value = float(t.value) if '.' in t.value else int(t.value)
    return t

def t_CADENA(t):
    r'".*?"'
    t.value = t.value[1:-1]
    return t

def t_COMENTARIO(t):
    r'\#.*'
    pass

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

# Lista para errores léxicos
errores = []
def t_error(t):
    columna = encontrar_columna(t)
    error_msg = f"[LEXICO] Caracter ilegal '{t.value[0]}' en linea {t.lineno}, columna {columna}"
    print(error_msg)
    errores.append(error_msg)
    t.lexer.skip(1)


def encontrar_columna(token):
    ultima_linea = token.lexer.lexdata.rfind('\n', 0, token.lexpos)
    if ultima_linea < 0:
        ultima_linea = -1
    return token.lexpos - ultima_linea

# Construcción del lexer
lexer = lex.lex()

# Generar bitácora en HTML
def generar_bitacora_html(tokens_lista, errores_lista, nombre_archivo="bitacora_errores.html"):
    simbolos = []
    for token in tokens_lista:
        if token.type == 'IDENTIFICADOR':
            simbolos.append((token.value, token.lineno, 'Variable Global'))
        elif token.type == 'MIENTRAS':
            simbolos.append((token.value, token.lineno, 'Inicio de Bucle'))
        elif token.type == 'IMPRIMIR':
            simbolos.append((token.value, token.lineno, 'Funcion'))
        elif token.type == 'RETORNAR':
            simbolos.append((token.value, token.lineno, 'Funcion'))
        elif token.type == 'LEER':
            simbolos.append((token.value, token.lineno, 'Funcion'))
        elif token.type == 'RANGO':
            simbolos.append((token.value, token.lineno, 'Funcion'))
        elif token.type == 'FUNC':
            simbolos.append((token.value, token.lineno, 'Funcion'))
        elif token.type == 'SI':
            simbolos.append((token.value, token.lineno, 'Inicio Condicion'))
        elif token.type == 'SINO':
            simbolos.append((token.value, token.lineno, 'Condicion Alternativa'))
        elif token.type == 'PARA':
            simbolos.append((token.value, token.lineno, 'Condicion'))


    with open(nombre_archivo, "w", encoding="utf-8") as f:
        f.write("<html><head><title>Bitacora de Errores</title></head><body>")
        f.write("<h2>Lista de Tokens</h2>")
        f.write("<table border='1'><tr><th>Tipo</th><th>Valor</th><th>Línea</th></tr>")
        for token in tokens_lista:
            f.write(f"<tr><td>{token.type}</td><td>{token.value}</td><td>{token.lineno}</td></tr>")
        f.write("</table>")

        f.write("<h2>Errores Lexicos y Sintacticos</h2>")
        f.write("<ul>")
        for error in errores_lista:
            f.write(f"<li>{error}</li>")
        f.write("</ul>")

        f.write("<h2>Tabla de Simbolos</h2>")
        f.write("<table border='1'><tr><th>Nombre</th><th>Línea</th><th>Tipo</th></tr>")
        for nombre, linea, tipo in simbolos:
            f.write(f"<tr><td>{nombre}</td><td>{linea}</td><td>{tipo}</td></tr>")
        f.write("</table>")

        f.write("</body></html>")
    print(f"Bitácora de errores generada: {nombre_archivo}")

def probar_lexer(codigo):
    global errores  # Aseguramos que se use la lista global de errores
    errores.clear()  # Limpiar errores anteriores
    lexer.input(codigo)
    tokens_lista = []
    for token in lexer:
        tokens_lista.append(token)
        print(token)
    generar_bitacora_html(tokens_lista, errores)  # Generar HTML con errores

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
        probar_lexer(codigo_leido)
    else:
        print("No se seleccionó ningún archivo.")

if __name__ == "__main__":
    main()