import sys
import resource
from .models import MathRequest
from .solver import solve

def main():
    resource.setrlimit(resource.RLIMIT_CPU, (5, 6))
    resource.setrlimit(resource.RLIMIT_AS, (1024 * 1024 * 1024, 1024 * 1024 * 1024))
    try:
        request = MathRequest.model_validate_json(sys.stdin.read(4096))
        print(solve(request).model_dump_json())
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
if __name__ == "__main__": main()
