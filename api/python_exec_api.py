# /api/python_exec_api.py
from flask import Blueprint, request, jsonify
from flask_restful import Api, Resource
import subprocess, tempfile, os

python_exec_api = Blueprint('python_exec_api', __name__, url_prefix='/run')
api = Api(python_exec_api)

class PythonExec(Resource):
    def post(self):
        """Executes submitted Python code safely in a short-lived subprocess."""
        data = request.get_json()
        code = data.get("code", "")

        if not code.strip():
            return {"output": "⚠️ No code provided."}, 400

        with tempfile.NamedTemporaryFile(delete=False, suffix=".py") as tmp:
            tmp.write(code.encode())
            tmp.flush()

            try:
                result = subprocess.run(
                    ["python3", tmp.name],
                    capture_output=True,
                    text=True,
                    timeout=5,
                    cwd="/tmp",  # Force working directory to /tmp
                    env={"HOME": "/tmp", "PATH": "/usr/bin:/usr/local/bin"}  # Restricted environment
                )
                output = result.stdout + result.stderr
            except subprocess.TimeoutExpired:
                output = "⏱️ Execution timed out (5 s limit)."
            except Exception as e:
                output = f"Error running code: {str(e)}"
            finally:
                os.unlink(tmp.name)

        return {"output": output}

api.add_resource(PythonExec, "/python")