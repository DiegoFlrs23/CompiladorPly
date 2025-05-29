import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext
import ply.yacc as yacc
import Lexer_Ply as lexer_module
from Parser import contexto, generar_bitacora_html
import os
import webbrowser

# Crear el parser
parser = yacc.yacc(module=__import__('Parser'))

def seleccionar_archivo():
    filepath = filedialog.askopenfilename(filetypes=[("Archivos de texto", "*.txt")])
    if filepath:
        with open(filepath, 'r', encoding='utf-8') as file:
            codigo = file.read()
        entrada_texto.delete("1.0", tk.END)
        entrada_texto.insert(tk.END, codigo)
        ventana.title(f"Compilador - {os.path.basename(filepath)}")

def analizar_codigo():
    codigo = entrada_texto.get("1.0", tk.END)
    contexto.reset()

    lexer_module.analizador_lexico.input(codigo)
    lexer_module.analizador_lexico.lexdata = codigo  # ¡AQUÍ ESTÁ EL PUNTO CLAVE!

    try:
        parser.parse(codigo, lexer=lexer_module.analizador_lexico)
        mostrar_resultado()
    except Exception as e:
        salida_texto.delete("1.0", tk.END)
        salida_texto.insert(tk.END, f"[Error al analizar] {e}")

def mostrar_resultado():
    salida_texto.delete("1.0", tk.END)
    salida_texto.insert(tk.END, "Código de Tres Direcciones:\n")
    for linea in contexto.codigo_tres_direcciones:
        salida_texto.insert(tk.END, linea + '\n')

    if contexto.errores:
        salida_texto.insert(tk.END, "\nErrores encontrados:\n")
        for err in contexto.errores:
            salida_texto.insert(tk.END, err + '\n')

def generar_reporte_html():
    try:
        file_path = "bitacora_compilacion.html"
        codigo_fuente = entrada_texto.get("1.0", tk.END)
        tokens = []  # Si no llevas tokens aún, pásalo vacío por ahora
        errores = contexto.errores
        codigo_optimizado = contexto.codigo_tres_direcciones
        codigo_cpp = contexto.generar_cpp()

        lexer_module.generar_bitacora_html(
            file_path,
            codigo_fuente,
            tokens,
            errores,
            codigo_optimizado,
            codigo_cpp
        )

        webbrowser.open(f"file://{os.path.abspath(file_path)}")

    except Exception as e:
        messagebox.showerror("Error", f"No se pudo generar el HTML.\n{e}")

def generar_cpp():
    try:
        cpp_code = contexto.generar_cpp()
        ventana_cpp = tk.Toplevel(ventana)
        ventana_cpp.title("Código C++ Generado")

        cpp_texto = scrolledtext.ScrolledText(ventana_cpp, width=100, height=30, bg="#f8f8f8")
        cpp_texto.pack()
        cpp_texto.insert(tk.END, cpp_code)
    except Exception as e:
        messagebox.showerror("Error", f"No se pudo generar el código C++.\n{e}")
def boton_estilo(nombre, comando):
    return tk.Button(
        frame_botones,
        text=nombre,
        command=comando,
        bg="#007acc",
        fg="white",
        activebackground="#005f9e",
        font=("Segoe UI", 10, "bold"),
        relief=tk.FLAT,
        padx=10,
        pady=5
    )

# --- GUI Principal ---
"""""
ventana = tk.Tk()
ventana.title("Compilador")

# Entrada de código
tk.Label(ventana, text="Código fuente:").pack()
entrada_texto = scrolledtext.ScrolledText(ventana, width=100, height=20)
entrada_texto.pack()
"""""

ventana = tk.Tk()
ventana.title("Compilador")
ventana.geometry("800x600")
ventana.configure(bg="#1e1e1e")
# Entrada de código
entrada_texto = scrolledtext.ScrolledText(
    ventana,
    wrap=tk.WORD,
    width=90,
    height=20,
    bg="#2e2e2e",
    fg="#ffffff",
    insertbackground="#ffffff",
    font=("Consolas", 12),
    relief=tk.FLAT
)
entrada_texto.pack(padx=10, pady=10)


# Botones
frame_botones = tk.Frame(ventana)
frame_botones.pack()

#tk.Button(botones, text="Seleccionar archivo", command=seleccionar_archivo).pack(side=tk.LEFT, padx=5)
#tk.Button(botones, text="Analizar", command=analizar_codigo).pack(side=tk.LEFT, padx=5)
#tk.Button(botones, text="Ver reporte HTML", command=generar_reporte_html).pack(side=tk.LEFT, padx=5)
#tk.Button(botones, text="Ver código C++", command=generar_cpp).pack(side=tk.LEFT, padx=5)
boton_estilo("Seleccionar archivo", seleccionar_archivo).pack(side=tk.LEFT, padx=5)
boton_estilo( "Analizar", analizar_codigo).pack(side=tk.LEFT, padx=5)
boton_estilo( "Ver reporte HTML",generar_reporte_html).pack(side=tk.LEFT, padx=5)
boton_estilo( "Ver código C++", generar_cpp).pack(side=tk.LEFT, padx=5)



# Salida del compilador
#salida = scrolledtext.ScrolledText(ventana, wrap=tk.WORD, width=90, height=10, state='disabled', bg="#f0f0f0")
salida_texto = scrolledtext.ScrolledText(
 ventana,
    wrap=tk.WORD,
    width=90,
    height=10,
    bg="#121212",
    fg="#00FF00",
    insertbackground="#ffffff",
    font=("Consolas", 11),
    relief=tk.FLAT
)
salida_texto.pack(padx=10, pady=(0, 10))
#falta c++
ventana.mainloop()