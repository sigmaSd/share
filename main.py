import gi
gi.require_version('Adw', '1')
from gi.repository import Adw, Gtk, Gdk, Gio, GLib, GdkPixbuf
import qrcode
from PIL import Image
import io
import threading
import http.server
import socketserver
import random
import socket
import os
import tempfile
import signal

class FileServer:
    def __init__(self):
        self.port = random.randint(8000, 9000)
        self.file_path = None
        self.server = None
        self.thread = None

    def set_file(self, file_path):
        self.file_path = file_path

    def start(self):
        if self.server is None:
            handler = self.create_handler()
            self.server = socketserver.TCPServer(("", self.port), handler)
            self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.thread.start()
            print(f"Server started on port {self.port}")

    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join()
            self.server = None
            self.thread = None
            print("Server stopped")

    def create_handler(self):
        file_server = self
        class Handler(http.server.SimpleHTTPRequestHandler):
            def do_GET(self):
                if file_server.file_path and os.path.exists(file_server.file_path):
                    self.send_response(200)
                    self.send_header('Content-type', 'application/octet-stream')
                    self.send_header('Content-Disposition', f'attachment; filename="{os.path.basename(file_server.file_path)}"')
                    self.end_headers()
                    with open(file_server.file_path, 'rb') as file:
                        try:
                            self.wfile.write(file.read())
                        except:
                            print("Connection closed")
                else:
                    self.send_error(404, "File not found")
        return Handler

class FileDropArea(Adw.Bin):
    def __init__(self, file_server):
        super().__init__()
        self.file_server = file_server

        self.box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20)
        self.box.set_margin_top(30)
        self.box.set_margin_bottom(30)
        self.box.set_margin_start(30)
        self.box.set_margin_end(30)
        self.set_child(self.box)

        self.set_size_request(300, 300)

        self.label = Gtk.Label(label="Drop a file here")
        self.label.add_css_class("drop-label")
        self.box.append(self.label)

        self.image = Gtk.Picture()
        self.image.set_size_request(200, 200)
        self.box.append(self.image)

        self.drop_target = Gtk.DropTarget.new(Gio.File, Gdk.DragAction.COPY)
        self.drop_target.connect("drop", self.on_drop)
        self.add_controller(self.drop_target)

        self.add_css_class("drop-area")

        self.temp_dir = tempfile.mkdtemp()
        self.qr_path = os.path.join(self.temp_dir, "qr.png")

    def on_drop(self, drop_target, value, x, y):
        if isinstance(value, Gio.File):
            file_path = value.get_path()
            # if file path is None return
            if file_path is None:
                return False
            # if file path is directory return
            if os.path.isdir(file_path):
                self.show_error_dialog("Cannot accept directories. Please drop a file.")
                return False
            self.label.set_text(f"{file_path}")
            self.generate_qr_code(file_path)
            return True
        return False

    def generate_qr_code(self, file_path):
        self.file_server.set_file(file_path)
        ip = self.get_local_ip()
        url = f"http://{ip}:{self.file_server.port}/{os.path.basename(file_path)}"
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(url)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        img.save(self.qr_path)
        self.image.set_filename(self.qr_path)

    def get_local_ip(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(('10.255.255.255', 1))
            IP = s.getsockname()[0]
        except Exception:
            IP = '127.0.0.1'
        finally:
            s.close()
        return IP

    def show_error_dialog(self, message):
        dialog = Gtk.MessageDialog(
            transient_for=self.get_root(),
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text=message
        )
        dialog.connect("response", lambda dialog, response: dialog.destroy())
        dialog.set_visible(True)

class MainWindow(Gtk.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.set_title("File Drop QR Code Generator")
        self.set_default_size(400, 500)

        self.set_hide_on_close(False)

        header = Adw.HeaderBar()
        self.set_titlebar(header)

        self.content = Adw.Clamp()
        self.set_child(self.content)

        self.file_server = FileServer()
        self.box = FileDropArea(self.file_server)
        self.content.set_child(self.box)
        self.file_server.start()

        self.load_css()

    def load_css(self):
        css_provider = Gtk.CssProvider()
        css = b"""
        .drop-area {
            background-color: #f0f0f0;
            border: 2px dashed #999;
            border-radius: 10px;
        }
        .drop-label {
            font-size: 18px;
            font-weight: bold;
            color: #555;
        }
        """
        css_provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def do_close_request(self):
        self.file_server.stop()
        return False

class MyApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)
        signal.signal(signal.SIGINT, self.signal_handler)

    def on_activate(self, app):
        win = MainWindow(application=self)
        win.present()

    def signal_handler(self, signum, frame):
        print("\nReceived Ctrl+C. Cleaning up and exiting...")
        self.quit()

app = MyApp(application_id="com.example.AdwApplication")
app.run(None)
