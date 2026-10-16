import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { fetchProduct, formatPrice } from "../api";
import type { Product } from "../types";

export default function ProductDetail() {
  const { productId } = useParams<{ productId: string }>();
  const [product, setProduct] = useState<Product | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!productId) return;
    setProduct(null);
    setError(null);
    fetchProduct(productId).then(setProduct).catch((e: Error) => setError(e.message));
  }, [productId]);

  if (error) return <p className="error">Couldn't load product: {error}</p>;
  if (!product) return <p>Loading…</p>;

  return (
    <>
      <Link to="/products" className="back">
        ← All products
      </Link>
      <div className="detail">
        <img className="detail-image" src={product.image_url} alt={product.name} />
        <div className="detail-text">
          <h1>{product.name}</h1>
          <p className="price">{formatPrice(product.price)}</p>
          <p>{product.description}</p>
          {product.colors.length > 0 && (
            <p>
              <strong>Colors:</strong> {product.colors.join(", ")}
            </p>
          )}
          {product.sizes && product.sizes.length > 0 && (
            <>
              <h2>Sizes &amp; stock</h2>
              <ul className="sizes">
                {product.sizes.map((s) => (
                  <li key={s.size} className={s.quantity === 0 ? "out" : ""}>
                    <strong>{s.size}</strong>
                    <span>{s.quantity === 0 ? "Out of stock" : `${s.quantity} in stock`}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      </div>
    </>
  );
}
