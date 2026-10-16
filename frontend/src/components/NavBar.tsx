import { NavLink, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";

const links = [
  { to: "/", label: "Home", end: true },
  { to: "/products", label: "Products" },
  { to: "/about", label: "About Us" },
  { to: "/guestbook", label: "Guestbook" },
];

export default function NavBar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function onLogout() {
    logout();
    navigate("/");
  }

  return (
    <header className="navbar">
      <div className="title-bar">
        <span className="title-bar-text">CAMPUSCUSTOMS.EXE</span>
        <div className="win-controls" aria-hidden="true">
          <span>_</span>
          <span>□</span>
          <span>X</span>
        </div>
      </div>
      <nav className="menu-bar">
        {links.map((l) => (
          <NavLink key={l.to} to={l.to} end={l.end}>
            {l.label}
          </NavLink>
        ))}
        {user ? (
          <>
            <span className="nav-greeting">hi, {user.first_name ?? user.name}</span>
            <button className="nav-logout" onClick={onLogout}>
              log out
            </button>
          </>
        ) : (
          <>
            <NavLink to="/login">log in</NavLink>
            <NavLink to="/create-account">create account</NavLink>
          </>
        )}
      </nav>
    </header>
  );
}
