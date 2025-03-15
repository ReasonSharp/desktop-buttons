#!/usr/bin/env python3
import http.server

class Handler(http.server.SimpleHTTPRequestHandler):
 def get_environ(self, method):
  path_info, _, query_string = self.path.partition("?")
  environ = {
   "REQUEST_METHOD": method,
   "PATH_INFO": path_info,
   "QUERY_STRING": query_string,
   "SERVER_PROTOCOL": self.protocol_version,
   "HTTP_HOST": self.headers.get("Host", "localhost:8000"),
   "wsgi.version": (1, 0),
   "wsgi.url_scheme": "http",
   "wsgi.input": self.rfile,
   "wsgi.errors": self.wfile,
   "wsgi.multithread": True,
   "wsgi.multiprocess": False,
   "wsgi.run_once": False,
  }
  if method == "POST":
   environ[f"CONTENT_LENGTH"] = self.headers.get("Content-Length", "0")
   environ[f"CONTENT_TYPE"] = self.headers.get("Content-Type", "")
  for header, value in self.headers.items():
   environ[f"HTTP_{header.upper().replace('-', '_')}"] = value
  return environ

 def respond(self, method):
  environ = self.get_environ(method)
  def start_response(status, headers):
   self.send_response(int(status.split()[0]))
   for key, value in headers:
    self.send_header(key, value)
   self.end_headers()
  response = self.server.app.wsgi_app(environ, start_response)
  if response:
   self.wfile.write(b"".join(response))

 def serve(self, method):
  if self.path.startswith("/api/"):
   self.respond(method)
  else:
   if method == "GET":
    super().do_GET()
   else:
    self.send_response(405)
    self.end_headers()

 def do_GET(self):
  self.serve("GET")

 def do_POST(self):
  self.serve("POST")

 def do_DELETE(self):
  self.serve("DELETE")