#!/usr/bin/env python3
"""
Hermes Host Proxy v1.4 - 使用 select 实现双向转发，避免线程竞争。
"""
import logging, select, socket, socketserver, sys
from urllib.parse import urlparse

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [PROXY] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("host_proxy")

PROXY_PORT = 18931
BUFFER_SIZE = 65536


def tunnel(client: socket.socket, remote: socket.socket):
    """select 双向转发，直到一端关闭。"""
    client.setblocking(False)
    remote.setblocking(False)
    done = False
    while not done:
        rlist, _, _ = select.select([client, remote], [], [], 30)
        if not rlist:
            break  # timeout
        for src in rlist:
            dst = remote if src is client else client
            try:
                data = src.recv(BUFFER_SIZE)
                if not data:
                    done = True
                    break
                dst.sendall(data)
            except:
                done = True
                break


class ProxyHandler(socketserver.BaseRequestHandler):
    def handle(self):
        addr = self.client_address
        try:
            data = self.request.recv(BUFFER_SIZE)
            if not data:
                return
            line = data.split(b"\r\n")[0].decode("utf-8", errors="replace")
            parts = line.split()
            if len(parts) < 3:
                return
            method, target = parts[0], parts[1]

            if method == "CONNECT":
                host, _, ps = target.partition(":")
                port = int(ps) if ps else 443
                logger.info(f"CONNECT {host}:{port} ← {addr}")
                try:
                    remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote.settimeout(15)
                    remote.connect((host, port))
                    self.request.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                    tunnel(self.request, remote)
                except Exception as e:
                    logger.warning(f"CONNECT {host}:{port}: {e}")
                    try: self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    except: pass
                finally:
                    try: remote.close()
                    except: pass

            elif method in ("GET", "POST", "PUT", "DELETE", "HEAD", "PATCH", "OPTIONS"):
                parsed = urlparse(target)
                host = parsed.hostname
                port = parsed.port or (80 if parsed.scheme != "https" else 443)
                path = parsed.path or "/"
                if parsed.query:
                    path += "?" + parsed.query
                logger.info(f"HTTP {method} {host}:{port}{path} ← {addr}")
                try:
                    remote = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    remote.settimeout(30)
                    remote.connect((host, port))
                    req = f"{method} {path} HTTP/1.1\r\n".encode()
                    rest = data.split(b"\r\n", 1)[1] if b"\r\n" in data else b""
                    remote.sendall(req + rest)
                    tunnel(remote, self.request)
                except Exception as e:
                    logger.warning(f"HTTP {host}:{port}: {e}")
                    try: self.request.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    except: pass
                finally:
                    try: remote.close()
                    except: pass
            else:
                self.request.sendall(b"HTTP/1.1 501 Not Implemented\r\n\r\n")
        except:
            pass


class ThreadedProxy(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def main():
    server = ThreadedProxy(("127.0.0.1", PROXY_PORT), ProxyHandler)
    print(f"Hermes Proxy: http://127.0.0.1:{PROXY_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
