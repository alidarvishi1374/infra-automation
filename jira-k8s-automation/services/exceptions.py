class KubernetesError(Exception):
    def __init__(self, message, error_type="unknown"):
        super().__init__(message)
        self.error_type = error_type
        self.message = message