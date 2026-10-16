import { Link } from "react-router-dom";

export default function Home() {
  return (
    <section className="hero">
      <h1 data-text="Campus Customs">Campus Customs</h1>
      <p>literally the only store fr fr. hoodies, crewnecks, tees and more.</p>
      <Link to="/products" className="btn">
        Shop Products
      </Link>
    </section>
  );
}
