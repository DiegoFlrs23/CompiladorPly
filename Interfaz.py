import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
from Parser import probar_parser
import webbrowser
import os


def limpiar_salida():
    salida.config(state='normal')
    salida.delete("1.0", tk.END)
    salida.config(state='disabled')


def ejecutar_compilador():
    codigo = entrada.get("1.0", tk.END)
    if not codigo.strip():
        messagebox.showwarning("Aviso", "El código está vacío.")
        return

    resultado = probar_parser(codigo)

    salida.config(state='normal')
    salida.delete("1.0", tk.END)
    salida.insert(tk.END, resultado)
    salida.config(state='disabled')
def abrir_bitacora_html():
    archivo = "bitacora_errores.html"
    if os.path.exists(archivo):
        webbrowser.open_new_tab(archivo)
    else:
        messagebox.showerror("Error", "La bitácora HTML no ha sido generada aún.")
def cargar_archivo():
    archivo = filedialog.askopenfilename(
        title="Abrir archivo",
        filetypes=[("Archivos de texto", "*.txt *.java"), ("Todos los archivos", "*.*")]
    )
    if archivo:
        with open(archivo, 'r', encoding='utf-8') as f:
            contenido = f.read()
            entrada.delete("1.0", tk.END)
            entrada.insert(tk.END, contenido)

def guardar_resultado():
    contenido = salida.get("1.0", tk.END).strip()
    if not contenido:
        messagebox.showinfo("Guardar", "No hay nada que guardar.")
        return

    archivo = filedialog.asksaveasfilename(
        title="Guardar resultado",
        defaultextension=".txt",
        filetypes=[("Archivos de texto", "*.txt")]
    )
    if archivo:
        with open(archivo, 'w', encoding='utf-8') as f:
            f.write(contenido)
        messagebox.showinfo("Guardado", f"Resultado guardado en {archivo}")

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
# Ventana principal
ventana = tk.Tk()
ventana.title("Compilador")
ventana.geometry("800x600")
ventana.configure(bg="#1e1e1e")
# Entrada de código
entrada = scrolledtext.ScrolledText(
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
entrada.pack(padx=10, pady=10)


# Botones
frame_botones = tk.Frame(ventana)
frame_botones.pack()
boton_estilo("Compilar", ejecutar_compilador).pack(side=tk.LEFT, padx=5)
boton_estilo("Cargar archivo", cargar_archivo).pack(side=tk.LEFT, padx=5)
boton_estilo("Guardar resultado", guardar_resultado).pack(side=tk.LEFT, padx=5)
boton_estilo("Ver bitácora HTML", abrir_bitacora_html).pack(side=tk.LEFT, padx=5)
boton_estilo("Limpiar salida", limpiar_salida).pack(side=tk.LEFT, padx=5)
#tk.Button(frame_botones, text="Compilar", command=ejecutar_compilador).pack(side=tk.LEFT, padx=5)
#tk.Button(frame_botones, text="Cargar archivo", command=cargar_archivo).pack(side=tk.LEFT, padx=5)
#tk.Button(frame_botones, text="Guardar resultado", command=guardar_resultado).pack(side=tk.LEFT, padx=5)
#tk.Button(frame_botones, text="Ver bitácora HTML", command=abrir_bitacora_html).pack(side=tk.LEFT, padx=5)

# Salida del compilador
#salida = scrolledtext.ScrolledText(ventana, wrap=tk.WORD, width=90, height=10, state='disabled', bg="#f0f0f0")
salida = scrolledtext.ScrolledText(
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
salida.pack(padx=10, pady=(0, 10))
#falta c++
ventana.mainloop()
