"""
app/models/product.py — Modelos de Produto e Categorias

Define produtos, categorias, marcas e o controlo de stock.
"""

from datetime import datetime, timezone
from decimal import Decimal
from app.extensions import db


class Category(db.Model):
    """Categoria de produtos (ex: Computadores, Impressoras, Redes)."""
    
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    description = db.Column(db.String(250), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    products = db.relationship('Product', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<Category {self.name}>'


class Brand(db.Model):
    """Marcas de produtos (ex: HP, Dell, Lenovo)."""
    
    __tablename__ = 'brands'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True, index=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    products = db.relationship('Product', backref='brand', lazy='dynamic')
    
    def __repr__(self):
        return f'<Brand {self.name}>'


class Product(db.Model):
    """
    Modelo de produto do TechNexus.
    
    Armazena materiais e equipamentos informáticos.
    O custo médio ponderado é actualizado em cada entrada de stock.
    """
    
    __tablename__ = 'products'
    
    # ==========================================
    # Identificação
    # ==========================================
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String(50), unique=True, nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    description = db.Column(db.Text, nullable=True)
    model = db.Column(db.String(100), nullable=True)
    
    # Chaves estrangeiras para categoria e marca
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    brand_id = db.Column(db.Integer, db.ForeignKey('brands.id'), nullable=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=True)
    
    # ==========================================
    # Unidade de medida
    # ==========================================
    unit = db.Column(db.String(20), nullable=False, default='unidade')
    
    # ==========================================
    # Preços (em NUMERIC para evitar erros de arredondamento)
    # ==========================================
    # Custo de compra actual (último preço pago)
    purchase_price = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    # Custo médio ponderado (para calcular CPV correctamente)
    average_cost = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    # Preço de venda definido
    selling_price = db.Column(db.Numeric(15, 2), nullable=False, default=0)
    
    # ==========================================
    # Stock
    # ==========================================
    stock_quantity = db.Column(db.Numeric(15, 3), nullable=False, default=0)
    minimum_stock = db.Column(db.Numeric(15, 3), nullable=False, default=5)
    
    # Indica se este produto tem controlo por número de série
    has_serial_number = db.Column(db.Boolean, default=False, nullable=False)
    
    # ==========================================
    # Estado
    # ==========================================
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    
    # ==========================================
    # Auditoria
    # ==========================================
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # ==========================================
    # Relacionamentos
    # ==========================================
    stock_movements = db.relationship('StockMovement', backref='product', lazy='dynamic')
    serial_numbers = db.relationship('ProductSerialNumber', backref='product', lazy='dynamic')
    sale_items = db.relationship('SaleItem', backref='product', lazy='dynamic')
    purchase_items = db.relationship('PurchaseItem', backref='product', lazy='dynamic')
    
    def __repr__(self):
        return f'<Product {self.sku}: {self.name}>'
    
    # ==========================================
    # Cálculos de margem
    # ==========================================
    
    @property
    def gross_profit_unit(self):
        """
        Lucro bruto unitário.
        Fórmula: preço de venda - custo médio ponderado
        """
        selling = Decimal(str(self.selling_price or 0))
        cost = Decimal(str(self.average_cost or 0))
        return float(selling - cost)
    
    @property
    def gross_margin_percent(self):
        """
        Margem bruta em percentagem.
        Fórmula: (preço venda - custo) / preço venda × 100
        Retorna None se o preço de venda for zero.
        """
        selling = Decimal(str(self.selling_price or 0))
        if selling == 0:
            return None  # Evita divisão por zero
        cost = Decimal(str(self.average_cost or 0))
        return float((selling - cost) / selling * 100)
    
    @property
    def markup_percent(self):
        """
        Acréscimo sobre o custo (markup).
        Fórmula: (preço venda - custo) / custo × 100
        NOTA: Diferente da margem bruta!
        """
        cost = Decimal(str(self.average_cost or 0))
        if cost == 0:
            return None
        selling = Decimal(str(self.selling_price or 0))
        return float((selling - cost) / cost * 100)
    
    @property
    def is_below_minimum_stock(self):
        """Verifica se o stock está abaixo do mínimo definido."""
        return float(self.stock_quantity or 0) < float(self.minimum_stock or 0)
    
    @property
    def is_out_of_stock(self):
        """Verifica se o produto está sem stock."""
        return float(self.stock_quantity or 0) <= 0
    
    @property
    def is_selling_below_cost(self):
        """Alerta se o preço de venda for inferior ao custo."""
        selling = Decimal(str(self.selling_price or 0))
        cost = Decimal(str(self.average_cost or 0))
        return selling < cost and selling > 0
    
    def update_average_cost(self, new_quantity, new_cost):
        """
        Actualiza o custo médio ponderado móvel após uma entrada de stock.
        
        Fórmula:
        Custo médio = (quantidade actual × custo actual + nova quantidade × novo custo)
                      / (quantidade actual + nova quantidade)
        
        Parâmetros:
            new_quantity: Quantidade de produtos recebidos.
            new_cost: Custo unitário dos novos produtos.
        """
        current_qty = Decimal(str(self.stock_quantity or 0))
        current_cost = Decimal(str(self.average_cost or 0))
        new_qty = Decimal(str(new_quantity))
        new_unit_cost = Decimal(str(new_cost))
        
        total_qty = current_qty + new_qty
        
        if total_qty > 0:
            # Calcula o custo médio ponderado
            total_value = (current_qty * current_cost) + (new_qty * new_unit_cost)
            self.average_cost = total_value / total_qty
        
        # Actualiza o preço de compra mais recente
        self.purchase_price = new_unit_cost
    
    def to_dict(self):
        return {
            'id': self.id,
            'sku': self.sku,
            'name': self.name,
            'category_id': self.category_id,
            'brand_id': self.brand_id,
            'purchase_price': float(self.purchase_price or 0),
            'average_cost': float(self.average_cost or 0),
            'selling_price': float(self.selling_price or 0),
            'stock_quantity': float(self.stock_quantity or 0),
            'minimum_stock': float(self.minimum_stock or 0),
            'gross_profit_unit': self.gross_profit_unit,
            'gross_margin_percent': self.gross_margin_percent,
            'is_active': self.is_active,
            'is_below_minimum_stock': self.is_below_minimum_stock,
        }


class ProductSerialNumber(db.Model):
    """
    Números de série para produtos que requerem controlo individual.
    Cada número de série identifica uma unidade física única.
    """
    
    __tablename__ = 'product_serial_numbers'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    serial_number = db.Column(db.String(100), nullable=False)
    
    # Estado: 'in_stock', 'sold', 'returned', 'damaged'
    status = db.Column(db.String(20), nullable=False, default='in_stock')
    
    # Referências às operações de entrada e saída
    purchase_item_id = db.Column(db.Integer, db.ForeignKey('purchase_items.id'), nullable=True)
    sale_item_id = db.Column(db.Integer, db.ForeignKey('sale_items.id'), nullable=True)
    
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Garante que não existem números de série duplicados por produto
    __table_args__ = (
        db.UniqueConstraint('product_id', 'serial_number', name='uq_product_serial'),
    )
    
    def __repr__(self):
        return f'<SerialNumber {self.serial_number} ({self.status})>'


class StockMovement(db.Model):
    """
    Registo de todas as movimentações de stock.
    
    Tipos de movimento:
    - purchase_in: Entrada por compra
    - sale_out: Saída por venda
    - return_in: Entrada por devolução
    - return_out: Saída por devolução a fornecedor
    - adjustment_in: Ajuste de inventário (entrada)
    - adjustment_out: Ajuste de inventário (saída)
    - damaged: Produto danificado (saída)
    - transfer_in: Entrada por transferência
    - transfer_out: Saída por transferência
    """
    
    __tablename__ = 'stock_movements'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    
    # Tipo de movimento
    movement_type = db.Column(db.String(30), nullable=False, index=True)
    
    # Quantidade (sempre positiva; a direcção é definida pelo tipo)
    quantity = db.Column(db.Numeric(15, 3), nullable=False)
    
    # Custo unitário no momento do movimento (para o CPV)
    unit_cost = db.Column(db.Numeric(15, 2), nullable=True)
    
    # Stock antes e depois do movimento
    stock_before = db.Column(db.Numeric(15, 3), nullable=False)
    stock_after = db.Column(db.Numeric(15, 3), nullable=False)
    
    # Referências às operações que originaram o movimento
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    purchase_id = db.Column(db.Integer, db.ForeignKey('purchases.id'), nullable=True)
    service_order_id = db.Column(db.Integer, db.ForeignKey('service_orders.id'), nullable=True)
    
    # Motivo e observações
    reason = db.Column(db.String(250), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Auditoria
    created_at = db.Column(db.DateTime(timezone=True),
                           default=lambda: datetime.now(timezone.utc), nullable=False, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Indica se o movimento foi anulado
    is_cancelled = db.Column(db.Boolean, default=False, nullable=False)
    cancelled_at = db.Column(db.DateTime(timezone=True), nullable=True)
    cancelled_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    cancellation_reason = db.Column(db.String(250), nullable=True)
    
    def __repr__(self):
        return f'<StockMovement {self.movement_type} {self.quantity}>'
