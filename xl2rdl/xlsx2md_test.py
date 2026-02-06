from docling.document_converter import DocumentConverter

converter = DocumentConverter()
result = converter.convert("memorymap.xlsx")

md = result.document.export_to_markdown()
print(md)  