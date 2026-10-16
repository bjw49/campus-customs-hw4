import type { Product } from "../types";

/** Real-signal sticker badges: "going fast" from actual stock levels,
 * "trending" from actual chat demand - not random meme text. */
export default function StickerBadges({ product }: { product: Product }) {
  if (!product.going_fast && !product.trending) return null;
  return (
    <>
      {product.trending && <span className="sticker-badge sticker-trending">trending</span>}
      {product.going_fast && <span className="sticker-badge sticker-going-fast">going fast</span>}
    </>
  );
}
