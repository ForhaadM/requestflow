from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Book(BaseModel):
    title: str
    author: str
    available: bool = True

books = []

@app.get("/books")
def get_books():
    return books

@app.get("/books/{book_id}")
def get_book(book_id: int):
    return books[book_id]

@app.post("/books")
def create_book(book: Book):
    books.append(book)
    return {"message": "Book added", "book": book}