import os
import signal
from waitress import serve
from config.wsgi import application

if __name__ == '__main__':
    def stop_cleanly(signum, frame):
        # Waitress catches KeyboardInterrupt and waits for workers before closing sockets.
        raise KeyboardInterrupt

    for name in ['SIGINT', 'SIGTERM', 'SIGBREAK']:
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), stop_cleanly)
    port = int(os.environ.get('PORT', '4350'))
    public = os.environ.get('TRACKER_PUBLIC') == '1'
    host = os.environ.get('TRACKER_BIND_HOST', '127.0.0.1')
    if host not in {'127.0.0.1', '0.0.0.0'}:
        raise RuntimeError('TRACKER_BIND_HOST must be an explicit supported IPv4 bind address')
    threads = int(os.environ.get('TRACKER_THREADS', '4'))
    if not 1 <= threads <= 4:
        raise RuntimeError('TRACKER_THREADS must be between 1 and 4')
    proxy_options = {}
    if public:
        trusted_proxy = os.environ.get('TRACKER_TRUSTED_PROXY')
        if not trusted_proxy:
            raise RuntimeError('Set TRACKER_TRUSTED_PROXY only after verifying the hosting proxy boundary')
        proxy_options = {'trusted_proxy': trusted_proxy, 'trusted_proxy_headers': {'x-forwarded-proto'}, 'trusted_proxy_count': 1}
    serve(application, host=host, port=port, threads=threads, max_request_body_size=32768, expose_tracebacks=False, clear_untrusted_proxy_headers=True, **proxy_options)
