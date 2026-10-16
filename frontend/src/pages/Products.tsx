import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { fetchProducts, formatPrice } from "../api";
import StickerBadges from "../components/StickerBadges";
import type { Product } from "../types";

function shortDescription(text: string, max = 110) {
  return text.length <= max ? text : text.slice(0, max).replace(/\s+\S*$/, "") + "…";
}

type SortOrder = "name-asc" | "price-asc" | "price-desc";

function SkeletonCard() {
  return (
    <div className="card skeleton-card" aria-hidden="true">
      <div className="skeleton skeleton-image" />
      <div className="card-body">
        <div className="skeleton skeleton-line" style={{ width: "75%" }} />
        <div className="skeleton skeleton-line" style={{ width: "35%" }} />
        <div className="skeleton skeleton-line" style={{ width: "95%" }} />
        <div className="skeleton skeleton-line" style={{ width: "60%" }} />
      </div>
    </div>
  );
}

export default function Products() {
  const [products, setProducts] = useState<Product[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [garmentType, setGarmentType] = useState("all");
  const [sort, setSort] = useState<SortOrder>("name-asc");

  useEffect(() => {
    fetchProducts().then(setProducts).catch((e: Error) => setError(e.message));
  }, []);

  const garmentTypes = useMemo(() => {
    if (!products) return [];
    return Array.from(new Set(products.map((p) => p.garment_type))).sort();
  }, [products]);

  const visibleProducts = useMemo(() => {
    if (!products) return [];
    let list = products;

    if (garmentType !== "all") {
      list = list.filter((p) => p.garment_type === garmentType);
    }

    const query = search.trim().toLowerCase();
    if (query) {
      list = list.filter(
        (p) =>
          p.name.toLowerCase().includes(query) ||
          p.description.toLowerCase().includes(query) ||
          p.garment_type.toLowerCase().includes(query) ||
          p.colors.some((c) => c.toLowerCase().includes(query)),
      );
    }

    list = [...list].sort((a, b) => {
      if (sort === "price-asc") return a.price - b.price;
      if (sort === "price-desc") return b.price - a.price;
      return a.name.localeCompare(b.name);
    });

    return list;
  }, [products, search, garmentType, sort]);

  if (error) return <p className="error">Couldn't load products: {error}</p>;

  return (
    <>
      <h1>Products</h1>
      {!products ? (
        <div className="grid">
          {Array.from({ length: 8 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      ) : (
        <>
          <div className="product-controls">
            <input
              type="search"
              className="product-search"
              placeholder="Search products…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              aria-label="Search products"
            />
            <select
              value={garmentType}
              onChange={(e) => setGarmentType(e.target.value)}
              aria-label="Filter by garment type"
            >
              <option value="all">All types</option>
              {garmentTypes.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortOrder)}
              aria-label="Sort products"
            >
              <option value="name-asc">Name (A–Z)</option>
              <option value="price-asc">Price (low to high)</option>
              <option value="price-desc">Price (high to low)</option>
            </select>
          </div>
          <p className="product-count">
            {visibleProducts.length} of {products.length} products
          </p>
          {visibleProducts.length === 0 ? (
            <p>No products match your search.</p>
          ) : (
            <div className="grid">
              {visibleProducts.map((p) => (
                <Link key={p.product_id} to={`/products/${p.product_id}`} className="card">
                  <StickerBadges product={p} />
                  <img src={p.image_url} alt={p.name} loading="lazy" />
                  <div className="card-body">
                    <h2>{p.name}</h2>
                    <p className="price">{formatPrice(p.price)}</p>
                    <p className="desc">{shortDescription(p.description)}</p>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </>
      )}
    </>
  );
}
