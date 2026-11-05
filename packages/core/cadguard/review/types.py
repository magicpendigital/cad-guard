"""Kiểu lỗi chung, độc lập app/server để các entry point không tạo import vòng."""
LOCAL = "__local__"


class ReviewError(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status
