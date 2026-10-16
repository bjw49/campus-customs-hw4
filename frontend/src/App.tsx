import { Route, Routes } from "react-router-dom";
import NavBar from "./components/NavBar";
import ChatWidget from "./components/ChatWidget";
import HitCounter from "./components/HitCounter";
import MarqueeTicker from "./components/MarqueeTicker";
import Home from "./pages/Home";
import Products from "./pages/Products";
import ProductDetail from "./pages/ProductDetail";
import About from "./pages/About";
import AuthForm from "./pages/AuthForm";
import Guestbook from "./pages/Guestbook";

export default function App() {
  return (
    <>
      <NavBar />
      <MarqueeTicker />
      <main className="page">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/products" element={<Products />} />
          <Route path="/products/:productId" element={<ProductDetail />} />
          <Route path="/about" element={<About />} />
          <Route path="/login" element={<AuthForm mode="login" />} />
          <Route path="/create-account" element={<AuthForm mode="signup" />} />
          <Route path="/guestbook" element={<Guestbook />} />
          <Route path="*" element={<p>Page not found.</p>} />
        </Routes>
        <HitCounter />
      </main>
      <ChatWidget />
    </>
  );
}
