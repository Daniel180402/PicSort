import os
import shutil
import subprocess
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from datetime import datetime
import threading
import hashlib
from PIL import Image, ImageTk
import imagehash
import pickle

# Optional imports for advanced features
try:
    import face_recognition
    from sklearn.cluster import DBSCAN
    import numpy as np
    FACE_REC_AVAILABLE = True
except ImportError:
    FACE_REC_AVAILABLE = False

class PicSortApp:
    def __init__(self, root):
        self.root = root
        self.root.title("PicSort - Organize Your Memories")
        self.root.geometry("900x700")

        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Organizer
        self.organizer_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.organizer_frame, text="Organizer")
        self.setup_organizer_tab()

        # Tab 2: Visual Cleaner
        self.cleaner_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.cleaner_frame, text="Visual Cleaner")
        self.setup_cleaner_tab()
        
        # Tab 3: People (Face Rec)
        self.people_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.people_frame, text="People")
        self.setup_people_tab()

    # ==========================
    # Tab 1: Organizer Logic
    # ==========================
    def setup_organizer_tab(self):
        main_frame = ttk.Frame(self.organizer_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.source_dir = tk.StringVar()
        self.dest_dir = tk.StringVar()
        self.is_sorting = False

        # Header
        ttk.Label(main_frame, text="Sort & Rename", font=("Helvetica", 18, "bold")).pack(pady=10)

        # Source
        f1 = ttk.Frame(main_frame)
        f1.pack(fill=tk.X, pady=5)
        ttk.Label(f1, text="Source:").pack(side=tk.LEFT)
        ttk.Entry(f1, textvariable=self.source_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(f1, text="Browse", command=lambda: self.browse_dir(self.source_dir)).pack(side=tk.LEFT)

        # Destination
        f2 = ttk.Frame(main_frame)
        f2.pack(fill=tk.X, pady=5)
        ttk.Label(f2, text="Dest:   ").pack(side=tk.LEFT)
        ttk.Entry(f2, textvariable=self.dest_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(f2, text="Browse", command=lambda: self.browse_dir(self.dest_dir)).pack(side=tk.LEFT)

        # Start Button
        self.start_btn = ttk.Button(main_frame, text="Start Sorting", command=self.start_sorting_thread)
        self.start_btn.pack(pady=15)

        # Progress
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(main_frame, variable=self.progress_var, maximum=100)
        self.progress_bar.pack(fill=tk.X, pady=5)

        # Log
        self.log_text = tk.Text(main_frame, height=10, state=tk.DISABLED)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def browse_dir(self, var):
        path = filedialog.askdirectory()
        if path:
            var.set(path)

    def log(self, message):
        self.log_text.config(state=tk.NORMAL)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def calculate_hash(self, file_path):
        """Calculates MD5 hash of a file."""
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()

    from PIL import ExifTags

    def get_creation_date(self, file_path):
        """
        Tries to get the creation date in this order:
        1. EXIF 'DateTimeOriginal' (Photos, Cross-platform)
        2. macOS 'mdls' (Photos/Videos, Mac only)
        3. File modification time (Fallback)
        """
        # 1. Try EXIF
        if file_path.lower().endswith(('.jpg', '.jpeg', '.tiff', '.png')):
            try:
                img = Image.open(file_path)
                exif = img._getexif()
                if exif:
                    for key, val in exif.items():
                        if key in ExifTags.TAGS and ExifTags.TAGS[key] == 'DateTimeOriginal':
                            # Format: "YYYY:MM:DD HH:MM:SS"
                            return datetime.strptime(val, "%Y:%m:%d %H:%M:%S")
            except Exception:
                pass

        # 2. Try mdls (macOS)
        if hasattr(os, 'uname') and os.uname().sysname == 'Darwin':
            try:
                cmd = ['mdls', '-name', 'kMDItemContentCreationDate', '-raw', file_path]
                result = subprocess.run(cmd, capture_output=True, text=True)
                output = result.stdout.strip()
                if output and output != "(null)":
                    dt = datetime.strptime(output.strip(), "%Y-%m-%d %H:%M:%S %z")
                    return dt.astimezone(None)
            except Exception:
                pass
        
        # 3. Fallback to mtime
        return datetime.fromtimestamp(os.path.getmtime(file_path))

    def start_sorting_thread(self):
        if not self.source_dir.get() or not self.dest_dir.get():
            messagebox.showerror("Error", "Please select folders.")
            return
        if self.is_sorting: return
        self.is_sorting = True
        self.start_btn.config(state=tk.DISABLED)
        threading.Thread(target=self.sort_process, daemon=True).start()

    def sort_process(self):
        src = self.source_dir.get()
        dst = self.dest_dir.get()
        
        all_files = []
        for root, dirs, files in os.walk(src):
            for file in files:
                if file.startswith('.'): continue
                all_files.append(os.path.join(root, file))

        total = len(all_files)
        done = 0
        skipped = 0
        
        for file_path in all_files:
            try:
                date_obj = self.get_creation_date(file_path)
                year, month = date_obj.strftime("%Y"), date_obj.strftime("%m-%B")
                ts_name = date_obj.strftime("%Y-%m-%d_%H-%M-%S")
                
                target_dir = os.path.join(dst, year, month)
                os.makedirs(target_dir, exist_ok=True)
                
                name, ext = os.path.splitext(os.path.basename(file_path))
                final_path = os.path.join(target_dir, ts_name + ext)
                
                # Dedup Logic
                if os.path.exists(final_path):
                    if self.calculate_hash(file_path) == self.calculate_hash(final_path):
                        skipped += 1
                        done += 1
                        continue # Skip exact duplicate
                    
                    # Collision
                    c=1
                    while os.path.exists(final_path):
                         # If we find collision is same hash, skip
                         if self.calculate_hash(file_path) == self.calculate_hash(final_path):
                             skipped += 1
                             done += 1
                             break
                         
                         final_path = os.path.join(target_dir, f"{ts_name}_{c}{ext}")
                         c+=1
                    
                    if os.path.exists(final_path) and self.calculate_hash(file_path) == self.calculate_hash(final_path):
                         continue

                shutil.copy2(file_path, final_path)
                done += 1
                self.progress_var.set((done/total)*100)
            except Exception as e:
                self.log(f"Error: {e}")
        
        self.is_sorting = False
        self.start_btn.config(state=tk.NORMAL)
        self.log(f"Finished. Moved {done-skipped}, Skipped {skipped}")
        messagebox.showinfo("Done", "Sorting Complete")

    # ==========================
    # Tab 2: Visual Cleaner Logic
    # ==========================
    def setup_cleaner_tab(self):
        main_frame = ttk.Frame(self.cleaner_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.clean_dir = tk.StringVar()
        
        # Folder Select
        f1 = ttk.Frame(main_frame)
        f1.pack(fill=tk.X, pady=5)
        ttk.Label(f1, text="Folder to Scan:").pack(side=tk.LEFT)
        ttk.Entry(f1, textvariable=self.clean_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(f1, text="Browse", command=lambda: self.browse_dir(self.clean_dir)).pack(side=tk.LEFT)

        # Controls
        f2 = ttk.Frame(main_frame)
        f2.pack(fill=tk.X, pady=10)
        ttk.Button(f2, text="Scan for Similar Images", command=self.start_scan_thread).pack(side=tk.LEFT)
        
        self.scan_status = ttk.Label(f2, text="Ready")
        self.scan_status.pack(side=tk.LEFT, padx=10)

        # Results Area (Treeview)
        self.tree = ttk.Treeview(main_frame, columns=('Group', 'Path', 'Score'), show='headings')
        self.tree.heading('Group', text='Group ID')
        self.tree.heading('Path', text='File Path')
        self.tree.heading('Score', text='Similarity')
        self.tree.column('Group', width=50)
        self.tree.column('Path', width=400)
        self.tree.column('Score', width=80)
        self.tree.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Action Buttons
        f3 = ttk.Frame(main_frame)
        f3.pack(fill=tk.X, pady=5)
        ttk.Button(f3, text="Delete Selected", command=self.delete_selected).pack(side=tk.RIGHT)
        ttk.Button(f3, text="Open Selected", command=self.open_selected).pack(side=tk.RIGHT, padx=5)

    def start_scan_thread(self):
        if not self.clean_dir.get():
             messagebox.showerror("Error", "Select a folder first.")
             return
        threading.Thread(target=self.scan_similar, daemon=True).start()

    def scan_similar(self):
        folder = self.clean_dir.get()
        self.scan_status.config(text="Scanning...")
        
        image_files = []
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif')):
                    image_files.append(os.path.join(root, f))
        
        hashes = {} # {path: hash}
        self.scan_status.config(text=f"Hashing {len(image_files)} images...")
        
        for i, path in enumerate(image_files):
            try:
                img = Image.open(path)
                h = imagehash.dhash(img)
                hashes[path] = h
            except Exception:
                pass
            if i % 10 == 0: self.scan_status.config(text=f"Hashing {i}/{len(image_files)}...")

        # Find similiar
        self.scan_status.config(text="Comparing...")
        groups = []
        visited = set()
        
        paths = list(hashes.keys())
        for i in range(len(paths)):
            if paths[i] in visited: continue
            
            current_group = [paths[i]]
            visited.add(paths[i])
            
            h1 = hashes[paths[i]]
            
            for j in range(i+1, len(paths)):
                if paths[j] in visited: continue
                
                h2 = hashes[paths[j]]
                if h1 - h2 <= 5: # Threshold 5 for dhash
                    current_group.append(paths[j])
                    visited.add(paths[j])
            
            if len(current_group) > 1:
                groups.append(current_group)

        # Update UI
        self.tree.delete(*self.tree.get_children())
        for idx, group in enumerate(groups):
            for path in group:
                self.tree.insert('', 'end', values=(f"Group {idx+1}", path, "Similar"))
            self.tree.insert('', 'end', values=("", "", "")) # Spacer logic handled loosely

        self.scan_status.config(text=f"Found {len(groups)} groups of similar images.")

    def delete_selected(self):
        selected = self.tree.selection()
        if not selected: return
        
        if messagebox.askyesno("Confirm", f"Delete {len(selected)} files?"):
            for item in selected:
                vals = self.tree.item(item)['values']
                if vals and vals[1]:
                    try:
                        os.remove(vals[1])
                        self.tree.delete(item)
                    except Exception as e:
                        print(e)

    def open_selected(self):
        selected = self.tree.selection()
        for item in selected:
            vals = self.tree.item(item)['values']
            if vals and vals[1]:
                subprocess.call(['open', vals[1]])


    # ==========================
    # Tab 3: People Logic
    # ==========================
    def setup_people_tab(self):
        if not FACE_REC_AVAILABLE:
            ttk.Label(self.people_frame, text="Face Recognition libraries not installed.\npip install face_recognition scikit-learn cmake").pack(pady=50)
            return

        main_frame = ttk.Frame(self.people_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.people_dir = tk.StringVar()

        # Input
        f1 = ttk.Frame(main_frame)
        f1.pack(fill=tk.X, pady=5)
        ttk.Label(f1, text="Folder to Scan faces:").pack(side=tk.LEFT)
        ttk.Entry(f1, textvariable=self.people_dir).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(f1, text="Browse", command=lambda: self.browse_dir(self.people_dir)).pack(side=tk.LEFT)

        # Start
        f2 = ttk.Frame(main_frame)
        f2.pack(fill=tk.X, pady=10)
        self.btn_scan_faces = ttk.Button(f2, text="Scan for Faces", command=self.start_face_scan)
        self.btn_scan_faces.pack(side=tk.LEFT)
        self.face_status = ttk.Label(f2, text="Ready")
        self.face_status.pack(side=tk.LEFT, padx=10)

        # Gallery / List
        # Using a listbox for "Person 1", "Person 2" and a Treeview for their photos
        paned = tk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        # Left: People List
        f_left = ttk.Frame(paned)
        ttk.Label(f_left, text="People Found").pack()
        self.people_list = tk.Listbox(f_left, width=20)
        self.people_list.pack(fill=tk.BOTH, expand=True)
        self.people_list.bind('<<ListboxSelect>>', self.on_person_select)
        paned.add(f_left)

        # Right: Photos
        f_right = ttk.Frame(paned)
        ttk.Label(f_right, text="Photos of Selected Person").pack()
        self.person_photos_tree = ttk.Treeview(f_right, columns=('Path',), show='headings')
        self.person_photos_tree.heading('Path', text="File Path")
        self.person_photos_tree.pack(fill=tk.BOTH, expand=True)
        self.person_photos_tree.bind("<Double-1>", self.on_face_photo_dbl_click)
        paned.add(f_right)
        
        self.clusters = {} # {label_id: [file_paths]}

    def start_face_scan(self):
        if not self.people_dir.get():
            messagebox.showerror("Error", "Select a folder.")
            return
        threading.Thread(target=self.scan_faces, daemon=True).start()

    def scan_faces(self):
        folder = self.people_dir.get()
        self.face_status.config(text="Finding images...")
        
        image_files = []
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    image_files.append(os.path.join(root, f))
        
        encodings = []
        files_with_faces = []
        
        # 1. Detect and Encode
        count = 0 
        for img_path in image_files:
            count += 1
            if count % 5 == 0: self.face_status.config(text=f"Scanning {count}/{len(image_files)}...")
            
            try:
                image = face_recognition.load_image_file(img_path)
                # Ensure existing detection model logic or user-selected
                boxes = face_recognition.face_locations(image) # uses hog (cpu) by default, or cnn (gpu)
                
                if len(boxes) > 0:
                    # Get encodings
                    encs = face_recognition.face_encodings(image, boxes)
                    for enc in encs:
                        encodings.append(enc)
                        files_with_faces.append(img_path)
            except Exception:
                pass

        if not encodings:
            self.face_status.config(text="No faces found.")
            return

        # 2. Cluster
        self.face_status.config(text="Clustering faces...")
        # DBSCAN is good for this, commonly used with dlib encodings
        # metric='euclidean', eps=0.5 is standard for dlib 128d
        clt = DBSCAN(metric="euclidean", n_jobs=-1, eps=0.45, min_samples=2)
        clt.fit(encodings)

        # Group results
        labels = clt.labels_
        self.clusters = {}
        
        for label_id, file_path in zip(labels, files_with_faces):
            if label_id == -1: continue # Noise
            if label_id not in self.clusters:
                self.clusters[label_id] = []
            # Avoid dupes per person if multiple faces in same image mapped to same person? 
            # Or simpler: just append. 
            if file_path not in self.clusters[label_id]:
                self.clusters[label_id].append(file_path)

        # Update UI
        self.people_list.delete(0, tk.END)
        for label_id in self.clusters.keys():
            self.people_list.insert(tk.END, f"Person {label_id}")
        
        self.face_status.config(text=f"Found {len(self.clusters)} distinct people.")

    def on_person_select(self, event):
        selection = self.people_list.curselection()
        if not selection: return
        
        idx = selection[0]
        text = self.people_list.get(idx)
        label_id = int(text.split(" ")[1])
        
        files = self.clusters.get(label_id, [])
        
        self.person_photos_tree.delete(*self.person_photos_tree.get_children())
        for f in files:
            self.person_photos_tree.insert('', 'end', values=(f,))

    def on_face_photo_dbl_click(self, event):
        item = self.person_photos_tree.selection()[0]
        val = self.person_photos_tree.item(item)['values']
        if val:
            subprocess.call(['open', val[0]])

if __name__ == "__main__":
    root = tk.Tk()
    app = PicSortApp(root)
    root.mainloop()
