import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel

# --- MODELOS DE DATOS (Pydantic para validación y serialización API) ---

class ProductModel(BaseModel):
    id: int
    name: str
    price: float
    description: str

class OrderInput(BaseModel):
    id: int
    product_ids: List[int]  # Lista de IDs de productos

class OrderOutput(BaseModel):
    id: int
    products: List[ProductModel] # Detalle completo de productos
    total: float
    status: str = "pending"

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    product_ids: Optional[List[int]] = None

# --- ESTRUCTURAS DE DATOS ---

# 1. Árbol Binario de Búsqueda (BST) para Productos
class ProductNode:
    def __init__(self, data: ProductModel):
        self.data = data
        self.left = None # Hijo izquierdo (IDs menores)
        self.right = None # Hijo derecho (IDs mayores)

    def to_dict(self):
        return self.data.dict()
    
# El Árbol
class ProductBST:
    def __init__(self):
        self.root = None

    def insert(self, data: ProductModel):
        if not self.root:
            self.root = ProductNode(data)
        else:
            self._insert_recursive(self.root, data)

    def _insert_recursive(self, node, data):
        if data.id < node.data.id:
            if node.left is None:
                node.left = ProductNode(data)
            else:
                self._insert_recursive(node.left, data)
        elif data.id > node.data.id:
            if node.right is None:
                node.right = ProductNode(data)
            else:
                self._insert_recursive(node.right, data)
        else:
            # Si el ID ya existe, actualizamos datos o lanzamos error 
            node.data = data

    def search(self, product_id: int) -> Optional[ProductNode]:
        return self._search_recursive(self.root, product_id)

    def _search_recursive(self, node, product_id):
        if node is None or node.data.id == product_id:
            return node
        if product_id < node.data.id:
            return self._search_recursive(node.left, product_id)
        return self._search_recursive(node.right, product_id)

    # Serialización del árbol completo a una lista plana para guardar en JSON
    def serialize(self):
        products = []
        self._in_order_traversal(self.root, products)
        return products

    def _in_order_traversal(self, node, products):
        if node:
            self._in_order_traversal(node.left, products)
            products.append(node.data.dict())
            self._in_order_traversal(node.right, products)

# 2. Lista Enlazada para Pedidos
class OrderNode:
    def __init__(self, order_id: int, products: List[ProductModel], total: float):
        self.id = order_id
        self.products = products
        self.total = total
        self.status = "pending"
        self.next = None # Puntero al siguiente pedido

    def to_dict(self):
        return {
            "id": self.id,
            "products": [p.dict() for p in self.products],
            "total": self.total,
            "status": self.status
        }

# La Lista 
class OrderLinkedList:
    def __init__(self):
        self.head = None

    def create_order(self, order_id, products: List[ProductModel]):
        total_price = sum(p.price for p in products)
        new_node = OrderNode(order_id, products, total_price)
        
        if not self.head:
            self.head = new_node
        else:
            # Insertar al final
            current = self.head
            while current.next:
                current = current.next
            current.next = new_node
        return new_node

    def find_order(self, order_id) -> Optional[OrderNode]:
        current = self.head
        while current:
            if current.id == order_id:
                return current
            current = current.next
        return None

    def update_order(self, order_id, new_status=None, new_products=None):
        node = self.find_order(order_id)
        if node:
            if new_status:
                node.status = new_status
            if new_products:
                node.products = new_products
                node.total = sum(p.price for p in new_products)
            return node
        return None

    def delete_order(self, order_id):
        current = self.head
        prev = None
        while current:
            if current.id == order_id:
                if prev:
                    prev.next = current.next
                else:
                    self.head = current.next
                return True
            prev = current
            current = current.next
        return False

    def list_all(self):
        orders = []
        current = self.head
        while current:
            orders.append(current.to_dict())
            current = current.next
        return orders

# --- MANEJO DE DATOS (Persistencia JSON) ---

PRODUCT_FILE = "products.json"
ORDER_FILE = "orders.json"

product_tree = ProductBST()
order_list = OrderLinkedList()

def save_data():
    """Guarda las estructuras en archivo JSON"""
    # Guardar productos
    with open(PRODUCT_FILE, 'w') as f:
        json.dump(product_tree.serialize(), f, indent=4)
    
    # Guardar pedidos
    with open(ORDER_FILE, 'w') as f:
        json.dump(order_list.list_all(), f, indent=4)

def load_data():
    """Carga datos desde JSON al iniciar"""
    try:
        with open(PRODUCT_FILE, 'r') as f:
            data = json.load(f)
            for p_data in data:
                product_tree.insert(ProductModel(**p_data))
    except FileNotFoundError:
        pass # Archivo no existe aún

    try:
        with open(ORDER_FILE, 'r') as f:
            data = json.load(f)
            for o_data in data:
                # Reconstruir productos
                products = [ProductModel(**p) for p in o_data['products']]
                node = order_list.create_order(o_data['id'], products)
                node.status = o_data['status']
    except FileNotFoundError:
        pass

# --- API FASTAPI ---

app = FastAPI(
    title="Sistema de Gestión de Pedidos",
    description="API para gestionar productos (BST) y pedidos (Lista Enlazada)",
    version="1.0.0"
)

# Cargar datos al inicio
@app.on_event("startup")
def startup_event():
    load_data()

# Crear producto
@app.post("/products/", response_model=ProductModel, summary="Crear un nuevo producto", tags=["Productos"])
def create_product(product: ProductModel):
    if product_tree.search(product.id):
        raise HTTPException(status_code=400, detail="Producto con ese ID ya existe")
    product_tree.insert(product)
    save_data()
    return product

# Consultar producto por ID
@app.get("/products/{product_id}", response_model=ProductModel, summary="Consultar producto por ID", tags=["Productos"])
def get_product(product_id: int):
    node = product_tree.search(product_id)
    if not node:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    return node.data

# Actualizar un producto existente
@app.put("/products/{product_id}", summary="Actualizar producto existente", tags=["Productos"])
def update_product(product_id: int, updated_info: ProductModel):
    # Paso 1: Buscamos el nodo en el árbol
    node = product_tree.search(product_id)
    
    if not node:
        raise HTTPException(status_code=404, detail="Producto no encontrado")
    
    # IMPORTANTE: Nos aseguramos de que el usuario no esté intentando cambiar el ID
    # El ID del objeto nuevo debe coincidir con el que estamos buscando
    if updated_info.id != product_id:
        raise HTTPException(status_code=400, detail="No se permite cambiar el ID del producto")

    # Paso 2: Actualizamos los datos dentro del nodo
    # Reemplazamos los datos viejos con los nuevos
    node.data = updated_info
    
    # Paso 3: Guardamos los cambios en el archivo JSON
    save_data()
    
    return {"msg": "Producto actualizado correctamente", "data": node.data}


# Crear nuevo pedido
@app.post("/orders/", response_model=OrderOutput, summary="Crear un nuevo pedido", tags=["Pedidos"])
def create_order(order: OrderInput):
    # Validar que el pedido no exista
    if order_list.find_order(order.id):
         raise HTTPException(status_code=400, detail="ID de pedido ya existe")

    # Buscar los productos en el BST
    products_found = []
    for pid in order.product_ids:
        node = product_tree.search(pid)
        if not node:
            raise HTTPException(status_code=404, detail=f"Producto ID {pid} no encontrado")
        products_found.append(node.data)

    # Crear nodo en lista enlazada
    new_order_node = order_list.create_order(order.id, products_found)
    save_data()
    return new_order_node.to_dict()

# Consultar pedido por ID
@app.get("/orders/{order_id}", response_model=OrderOutput, summary="Consultar pedido por ID", tags=["Pedidos"])
def get_order(order_id: int):
    node = order_list.find_order(order_id)
    if not node:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return node.to_dict()

# Actualizar pedido
@app.put("/orders/{order_id}", response_model=OrderOutput, summary="Actualizar pedido", tags=["Pedidos"])
def update_order(order_id: int, update: OrderUpdate):
    products_found = None
    if update.product_ids:
        products_found = []
        for pid in update.product_ids:
            node = product_tree.search(pid)
            if not node:
                raise HTTPException(status_code=404, detail=f"Producto ID {pid} no encontrado")
            products_found.append(node.data)
            
    node = order_list.update_order(order_id, update.status, products_found)
    if not node:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    save_data()
    return node.to_dict()

# Eliminar pedido
@app.delete("/orders/{order_id}", summary="Eliminar pedido", tags=["Pedidos"])
def delete_order(order_id: int):
    success = order_list.delete_order(order_id)
    if not success:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    save_data()
    return {"detail": "Pedido eliminado correctamente"}

# Listar todos los pedidos
@app.get("/orders/", response_model=List[OrderOutput], summary="Listar todos los pedidos", tags=["Pedidos"])
def list_orders():
    return order_list.list_all()