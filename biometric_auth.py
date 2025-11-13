import os
import sqlite3
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import cv2
import numpy as np
from PIL import Image, ImageTk
import shutil

# Configurações
DB_FILE = 'users.db'
MATCH_THRESHOLD = 0.3
IMAGE_SIZE = (300, 300)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # C:\biometria
USERS_DIR = os.path.join(BASE_DIR, 'users')

# Inicializa banco de dados
def init_database():
    db_path = os.path.join(BASE_DIR, DB_FILE)
    
    if not os.path.exists(USERS_DIR):
        os.makedirs(USERS_DIR)
        print(f"Pasta 'users' criada em {USERS_DIR}")
    
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE Users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                role TEXT NOT NULL,
                access_level INTEGER NOT NULL,
                image_path TEXT NOT NULL,
                additional_images TEXT
            )
        ''')
        conn.commit()
        conn.close()
        print(f"Banco de dados inicializado em {db_path}")

# Pega usuários
def get_users():
    db_path = os.path.join(BASE_DIR, DB_FILE)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, role, access_level, image_path, additional_images FROM Users")
    users = cursor.fetchall()
    conn.close()
    return users

# Pré-processa imagem
def preprocess_image(image_path):
    print(f"Tentando carregar: {image_path}")
    if not os.path.exists(image_path):
        raise Exception(f"Arquivo não encontrado: {image_path}")
    try:
        img = cv2.imread(image_path)
        if img is None:
            raise Exception(f"Erro ao carregar '{image_path}'. Verifique o formato.")
        img = cv2.resize(img, IMAGE_SIZE)
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    except Exception as e:
        raise Exception(f"Erro ao processar {image_path}: {str(e)}")

# Autenticação
def authenticate(input_path, users):
    print(f"Autenticando com: {input_path}")
    input_img = preprocess_image(input_path)
    sift = cv2.SIFT_create()
    bf = cv2.BFMatcher(cv2.NORM_L2)
    input_kp, input_des = sift.detectAndCompute(input_img, None)
    print(f"Keypoints na entrada: {len(input_kp)}")

    for user_id, name, role, level, main_path, alt_paths in users:
        abs_main_path = os.path.normpath(main_path)
        print(f"Comparando com {name} ({role})")
        main_img = preprocess_image(abs_main_path)
        main_kp, main_des = sift.detectAndCompute(main_img, None)
        matches = bf.knnMatch(input_des, main_des, k=2)
        good_matches = [m for m, n in matches if m.distance < 0.7 * n.distance]
        similarity = len(good_matches) / max(len(input_kp), len(main_kp), 1)
        print(f"Similaridade principal: {similarity}")

        if similarity >= MATCH_THRESHOLD:
            return name, role, level

        if alt_paths:
            for alt_path in alt_paths.split(","):
                abs_alt_path = os.path.normpath(alt_path.strip())
                print(f"Comparando com variação: {abs_alt_path}")
                alt_img = preprocess_image(abs_alt_path)
                alt_kp, alt_des = sift.detectAndCompute(alt_img, None)
                matches = bf.knnMatch(input_des, alt_des, k=2)
                good_matches = [m for m, n in matches if m.distance < 0.7 * n.distance]
                similarity = len(good_matches) / max(len(input_kp), len(alt_kp), 1)
                print(f"Similaridade variação: {similarity}")
                if similarity >= MATCH_THRESHOLD:
                    return name, role, level

    return None, None, None

# Adiciona ou atualiza usuário
def add_or_update_user(name, role, access_level, main_image_path, alt_image_path=None):
    db_path = os.path.join(BASE_DIR, DB_FILE)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Verifica se o usuário já existe
    cursor.execute("SELECT id, image_path, additional_images FROM Users WHERE name = ?", (name,))
    existing_user = cursor.fetchone()
    
    # Garante que a pasta users exista
    if not os.path.exists(USERS_DIR):
        os.makedirs(USERS_DIR)
        print(f"Pasta 'users' recriada em {USERS_DIR}")
    
    # Copia a imagem principal
    base_name = os.path.basename(main_image_path)
    new_main_path = os.path.join(USERS_DIR, f"{name}_{base_name}")
    if os.path.exists(new_main_path):
        os.remove(new_main_path)  # Remove se já existir
    try:
        shutil.copy2(main_image_path, new_main_path)
        print(f"Imagem principal salva em: {new_main_path}")
    except Exception as e:
        raise Exception(f"Falha ao salvar imagem principal: {str(e)}")
    
    additional_images = new_main_path
    if alt_image_path and os.path.exists(alt_image_path):
        base_alt_name = os.path.basename(alt_image_path)
        new_alt_path = os.path.join(USERS_DIR, f"{name}_alt_{base_alt_name}")
        if os.path.exists(new_alt_path):
            os.remove(new_alt_path)  # Remove se já existir
        try:
            shutil.copy2(alt_image_path, new_alt_path)
            print(f"Imagem adicional salva em: {new_alt_path}")
            additional_images = f"{new_main_path},{new_alt_path}"
        except Exception as e:
            print(f"Erro ao salvar imagem adicional, continuando sem ela: {str(e)}")
    
    if existing_user:
        cursor.execute("UPDATE Users SET role = ?, access_level = ?, image_path = ?, additional_images = ? WHERE name = ?",
                       (role, access_level, new_main_path, additional_images, name))
    else:
        cursor.execute("INSERT INTO Users (name, role, access_level, image_path, additional_images) VALUES (?, ?, ?, ?, ?)",
                       (name, role, access_level, new_main_path, additional_images))
    
    conn.commit()
    conn.close()
    print(f"Usuário {name} cadastrado/atualizado com sucesso.")

# Dados por nível
def get_data(access_level):
    data = "=== Dados Acessíveis ===\n\n"
    if access_level >= 1:
        data += "Nível 1 - Funcionário:\n"
        data += "- Relatório Geral: 120 propriedades monitoradas.\n"
        data += "- Propriedade X (SP): Uso de agrotóxicos permitidos.\n"
        data += "- Impacto Ambiental: Baixo.\n\n"
    if access_level >= 2:
        data += "Nível 2 - Diretor:\n"
        data += "- Relatório Restrito: 15 propriedades irregulares.\n"
        data += "- Propriedade Y (MG): Uso de agrotóxicos proibidos.\n"
        data += "- Ações Pendentes: Inspeção em 20/10/2025.\n\n"
    if access_level >= 3:
        data += "Nível 3 - Administrador:\n"
        data += "- Relatório Confidencial: Estratégia Nacional.\n"
        data += "- Estatísticas: 45% em risco crítico.\n"
        data += "- Plano: Multas de R$ 10M até 2026.\n"
    return data

# Interface profissional
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Autenticação Biométrica - EcoCorp")
        self.geometry("700x600")
        self.configure(bg="#1e3a8a")
        
        self.logo = tk.Label(self, text="EcoCorp Biometric", font=("Helvetica", 24, "bold"), fg="white", bg="#1e3a8a")
        self.logo.pack(pady=10)
        
        frame = ttk.Frame(self, padding="15", style="Custom.TFrame")
        frame.pack(fill="both", expand=True)
        
        style = ttk.Style()
        style.configure("Custom.TFrame", background="#f9fafb")
        style.configure("TButton", font=("Helvetica", 12), padding=8)
        style.map("TButton", background=[("active", "#2d6a4f")], foreground=[("active", "white")])
        
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=10)
        self.btn_auth = ttk.Button(btn_frame, text="Autenticar", command=self.do_auth, style="TButton")
        self.btn_auth.pack(side="left", padx=5)
        self.btn_add = ttk.Button(btn_frame, text="Cadastrar Usuário", command=self.show_add_user, style="TButton")
        self.btn_add.pack(side="left", padx=5)
        
        self.lbl_status = tk.Label(frame, text="Pronto para autenticação.", font=("Helvetica", 10), fg="#10b981", bg="#f9fafb")
        self.lbl_status.pack(pady=5)
        
        self.txt_data = scrolledtext.ScrolledText(frame, height=15, width=80, font=("Helvetica", 10), bg="#ffffff", fg="#1f2937")
        self.txt_data.pack(pady=10)
        self.txt_data.config(state="disabled")
        
        ttk.Button(frame, text="Sair", command=self.logout, style="TButton").pack(pady=5)
        
        init_database()

    def show_add_user(self):
        add_window = tk.Toplevel(self)
        add_window.title("Cadastrar Novo Usuário - EcoCorp")
        add_window.geometry("450x400")
        add_window.configure(bg="#f9fafb")
        add_window.transient(self)  # Mantém a janela no topo da janela principal
        add_window.grab_set()  # Impede interação com outras janelas até fechar esta
        
        # Layout em grade
        main_frame = ttk.Frame(add_window, padding="10", style="Custom.TFrame")
        main_frame.pack(fill="both", expand=True)
        
        # Campos
        tk.Label(main_frame, text="Nome:", bg="#f9fafb", font=("Helvetica", 10)).grid(row=0, column=0, pady=5, sticky="e")
        name_entry = tk.Entry(main_frame, font=("Helvetica", 10), width=30)
        name_entry.grid(row=0, column=1, pady=5, padx=5)
        
        tk.Label(main_frame, text="Cargo:", bg="#f9fafb", font=("Helvetica", 10)).grid(row=1, column=0, pady=5, sticky="e")
        role_entry = tk.Entry(main_frame, font=("Helvetica", 10), width=30)
        role_entry.grid(row=1, column=1, pady=5, padx=5)
        
        tk.Label(main_frame, text="Nível de Acesso (1-3):", bg="#f9fafb", font=("Helvetica", 10)).grid(row=2, column=0, pady=5, sticky="e")
        level_entry = tk.Entry(main_frame, font=("Helvetica", 10), width=30)
        level_entry.grid(row=2, column=1, pady=5, padx=5)
        
        tk.Label(main_frame, text="Imagem Principal:", bg="#f9fafb", font=("Helvetica", 10)).grid(row=3, column=0, pady=5, sticky="e")
        main_img_btn = ttk.Button(main_frame, text="Selecionar", command=lambda: self.select_image(add_window, main_img_var))
        main_img_btn.grid(row=3, column=1, pady=5, padx=5, sticky="w")
        main_img_var = tk.StringVar()
        tk.Label(main_frame, textvariable=main_img_var, bg="#f9fafb", font=("Helvetica", 9), wraplength=200).grid(row=4, column=1, pady=2, padx=5)
        
        tk.Label(main_frame, text="Imagem Adicional (opcional):", bg="#f9fafb", font=("Helvetica", 10)).grid(row=5, column=0, pady=5, sticky="e")
        alt_img_btn = ttk.Button(main_frame, text="Selecionar", command=lambda: self.select_image(add_window, alt_img_var))
        alt_img_btn.grid(row=5, column=1, pady=5, padx=5, sticky="w")
        alt_img_var = tk.StringVar()
        tk.Label(main_frame, textvariable=alt_img_var, bg="#f9fafb", font=("Helvetica", 9), wraplength=200).grid(row=6, column=1, pady=2, padx=5)
        
        # Botão de cadastro
        ttk.Button(main_frame, text="Cadastrar", command=lambda: self.save_user(add_window, name_entry, role_entry, level_entry, main_img_var, alt_img_var),
                   style="TButton").grid(row=7, column=0, columnspan=2, pady=15)
    
    def select_image(self, window, var):
        file_path = filedialog.askopenfilename(title="Selecione Imagem", filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp")])
        if file_path:
            var.set(file_path)
        window.lift()  # Mantém a janela no topo
        window.focus_force()  # Restaura o foco

    def save_user(self, window, name_entry, role_entry, level_entry, main_img_var, alt_img_var):
        name = name_entry.get().strip()
        role = role_entry.get().strip()
        try:
            level = int(level_entry.get())
            if not (1 <= level <= 3):
                raise ValueError
        except ValueError:
            messagebox.showerror("Erro", "Nível de acesso deve ser 1, 2 ou 3.")
            return
        main_path = main_img_var.get()
        alt_path = alt_img_var.get() if alt_img_var.get() else None
        
        if not name or not role or not main_path or not os.path.exists(main_path):
            messagebox.showerror("Erro", "Preencha todos os campos obrigatórios e selecione uma imagem válida.")
            return
        
        try:
            add_or_update_user(name, role, level, main_path, alt_path)
            messagebox.showinfo("Sucesso", f"Usuário {name} cadastrado com sucesso!")
            window.destroy()
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao cadastrar: {str(e)}")

    def do_auth(self):
        file_path = filedialog.askopenfilename(title="Selecione Imagem Biométrica", 
                                              filetypes=[("Imagens", "*.jpg *.jpeg *.png *.bmp *.tiff *.webp")])
        if not file_path:
            return
        
        self.lbl_status.config(text="Processando... ", fg="#f59e0b")
        for i in range(3):
            self.lbl_status.config(text=f"Processando{i+1}. ")
            self.update()
            self.after(300)
        self.update()
        
        try:
            if not os.path.exists(file_path):
                raise Exception(f"Arquivo não encontrado: {file_path}")
            users = get_users()
            name, role, level = authenticate(file_path, users)
            if name:
                self.lbl_status.config(text=f"Autenticado: {name} ({role})", fg="#10b981")
                data = get_data(level)
                self.txt_data.config(state="normal")
                self.txt_data.delete(1.0, tk.END)
                self.txt_data.insert(tk.END, data)
                self.txt_data.config(state="disabled")
            else:
                self.lbl_status.config(text="Autenticação falhou. Tente outra imagem.", fg="#ef4444")
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            self.lbl_status.config(text="Erro. Veja console.", fg="#ef4444")

    def clear(self):
        self.lbl_status.config(text="Pronto para autenticação.", fg="#10b981")
        self.txt_data.config(state="normal")
        self.txt_data.delete(1.0, tk.END)
        self.txt_data.config(state="disabled")

    def logout(self):
        self.clear()
        self.quit()  # Fecha a aplicação
        
if __name__ == "__main__":
    app = App()
    app.mainloop()