import sys
import os
import logging
import logging.handlers
from datetime import datetime
import uuid

from dotenv import load_dotenv


# Handler personalizado para flush inmediato en streams
class StreamFlushingHandler(logging.StreamHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

# Handler personalizado para flush inmediato en archivos
class FileFlushingHandler(logging.FileHandler):
    def emit(self, record):
        super().emit(record)
        self.flush()

class CustomLogFormatter(logging.Formatter):
    def format(self, record):
        module = getattr(record, 'module_name', 'UnknownModule')
        cliente = getattr(record, 'cliente', 'UnknownCliente')
        task_id = getattr(record, 'task_id', 'UnknownId')
        class_name = getattr(record, 'class_name', record.name).split('_')[0]
        result = getattr(record, 'result', 'UnknownResult')
        message = record.getMessage()
        loglevel = record.levelname
        date = self.formatTime(record, self.datefmt)
        return f"{module} - {date} - {cliente} - {task_id} - {class_name} - {loglevel} - {result} - {message}"


class LoggerV2:
    def __init__(
        self,
        module: str,
        class_name: str,
        log_dir: str = "logs",
        execution_id: str = None,
        filename: str = None,
        log_root: str = None,
        log_queue=None,
        handlers=None
    ):
        allowed_modules = {"Altas", "Descargas", "ConsultaEnotum", "MatriculasyPuntos", "SedeJudicial", "API", "Playground", "Benchmark" ,"UnknownModule"}
        self.execution_id = execution_id
        self.module = module if module in allowed_modules else "UnknownModule"
        self.class_name = class_name
        self.log_dir = log_dir
        self.filename = filename
        self.log_queue = log_queue
        self.handlers = handlers
        load_dotenv()
        network_path = os.getenv("NETWORK_PATH")

        def _is_valid_network_path(p: str) -> bool:
            if not p:
                return False
            s = str(p).strip()
            # Reject plain backslash sequences or obvious placeholders
            if s in ('', '\\', '//'):
                return False
            return True

        if log_root:
            resolved_log_root = log_root
        elif _is_valid_network_path(network_path):
            resolved_log_root = os.path.normpath(os.path.join(network_path, "Documents", "workspace", "redtrust-automation"))
        else:
            # Fallback to current working directory to avoid invalid UNC paths on Windows
            resolved_log_root = os.path.abspath(os.getcwd())

        self.logger = self._setup_logger(log_dir, filename, resolved_log_root, log_queue, handlers)

    def _setup_logger(self, log_dir: str, filename: str, log_root: str, log_queue=None, handlers=None) -> logging.Logger:
        load_dotenv(dotenv_path='.env', override=True)
        if self.module in ("API", "Playground", "UnknownModule"):
            hoy = datetime.now().strftime("%Y%m%d")
            filename = f"{self.module.lower()}_{hoy}"
        else:
            filename = f"{self.module.lower()}_{self.execution_id}" 

        logger = logging.getLogger(f"{self.class_name}.{uuid.uuid4().hex[:6]}")
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        logger.setLevel(getattr(logging, log_level, logging.INFO))

        if logger.handlers:
            return logger

        formatter = CustomLogFormatter(datefmt='%Y-%m-%d %H:%M')

        if handlers:
            for h in handlers:
                logger.addHandler(h)
        elif log_queue is not None:
            queue_handler = logging.handlers.QueueHandler(log_queue)
            queue_handler.setLevel(getattr(logging, log_level, logging.INFO))
            queue_handler.setFormatter(formatter)
            logger.addHandler(queue_handler)
        else:
            # File handler con flush inmediato
            full_log_dir = os.path.normpath(os.path.join(log_root, log_dir))
            try:
                os.makedirs(full_log_dir, exist_ok=True)
            except Exception:
                # If creation fails (e.g., invalid UNC path), fallback to a local logs folder
                fallback_dir = os.path.normpath(os.path.join(os.getcwd(), 'logs'))
                try:
                    os.makedirs(fallback_dir, exist_ok=True)
                    full_log_dir = fallback_dir
                except Exception:
                    # As a last resort, use current working directory
                    full_log_dir = os.getcwd()

            file_path = os.path.join(full_log_dir, f"log_{filename}.log")
            file_handler = FileFlushingHandler(file_path, mode='a', encoding='utf-8')
            file_handler.setLevel(getattr(logging, log_level, logging.INFO))
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            # Optional: console con flush inmediato
            if os.getenv("LOG_TO_CONSOLE", "true").lower() == "true":
                console_handler = StreamFlushingHandler(sys.stdout)
                console_handler.setLevel(getattr(logging, log_level, logging.INFO))
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)

        logger.propagate = False
        return logger

    def unmount(self):
        for handler in self.logger.handlers[:]:
            handler.close()
            self.logger.removeHandler(handler)

    def _log(self, cliente: str, task_id: str, result: str, level: str, message: str) -> None:
        allowed_results = {"Success", "Failure", "Info", "Pending", "UnknownResult"}
        result = result if result in allowed_results else "UnknownResult"
        extra = {
            'module_name': self.module,
            'cliente': cliente,
            'task_id': task_id,
            'class_name': self.class_name,
            'result': result
        }

        level = level.lower()
        if level == 'info':
            self.logger.info(message, extra=extra)
        elif level == 'warning':
            self.logger.warning(message, extra=extra)
        elif level == 'error':
            self.logger.error(message, extra=extra)
        elif level == 'debug':
            self.logger.debug(message, extra=extra)
        else:
            self.logger.info(message, extra=extra)

    # Interface methods
    def info(self, cliente: str, task_id: str, result: str, message: str = "UnknownMessage") -> None:
        self._log(cliente, task_id, result, 'info', message)

    def warning(self, cliente: str, task_id: str, result: str, message: str = "UnknownMessage") -> None:
        self._log(cliente, task_id, result, 'warning', message)

    def error(self, cliente: str, task_id: str, result: str, message: str = "UnknownMessage") -> None:
        self._log(cliente, task_id, result, 'error', message)

    def debug(self, cliente: str, task_id: str, result: str, message: str = "UnknownMessage") -> None:
        self._log(cliente, task_id, result, 'debug', message)