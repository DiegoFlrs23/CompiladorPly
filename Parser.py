from typing import ReadOnly
from urllib.request import OpenerDirector

import ply.yacc as yacc
from Lexer_Ply import tokens, errores, generar_bitacora_html
import tkinter as tk
from tkinter import filedialog
import ply.lex as lex
from Lexer_Ply import lexer

'''# Lista para errores sintácticos
errores_sintacticos = []'''
# Tabla de símbolos
tabla_simbolos = {}

# Reglas de la gramática
def p_programa(p):
    """programa : sentencias"""
    p[0] = p[1]

def p_sentencias(p):
    """sentencias : sentencia sentencias
                  | sentencia"""

def p_sentencia(p):
    """sentencia : asignacion
                 | imprimir
                 | condicion"""

# Reglas de asignación
def p_asignacion(p):
    """asignacion : IDENTIFICADOR IGUAL expresion"""
    tabla_simbolos[p[1]] = p[3]
    p[0] = (p[1], p[3])

# Reglas de expresiones
def p_expresion(p):
    """expresion : expresion MAS expresion
                 | expresion MENOS expresion
                 | expresion MULT expresion
                 | expresion DIV expresion
                 | NUMERO
                 | IDENTIFICADOR"""
    p[0] = p[1]

def p_imprimir(p):
    """imprimir : IMPRIMIR PARENTESIS_IZQ CADENA PARENTESIS_DER"""
    p[0] = p[3]

# Reglas para condicionales
def p_condicion(p):
    """condicion : SI PARENTESIS_IZQ expresion comparador expresion PARENTESIS_DER bloque"""

def p_comparador(p):
    """comparador : MAYOR
                   | MENOR
                   | MAYOR_IGUAL
                   | MENOR_IGUAL
                   | IGUAL_IGUAL
                   | DIFERENTE"""

def p_bloque(p):
    """bloque : LLAVE_IZQ sentencias LLAVE_DER"""

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

"""
# Código de prueba
test_code = 
x = 10;
y = x + 5;
imprimir("Hola");
si (x > y) { imprimir("x es mayor");}

#Inserción de Metodo de lectura de archivo


probar_parser(test_code)
"""