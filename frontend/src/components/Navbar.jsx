import { Link, useLocation } from 'react-router-dom';
import { BarChart3, History, Zap } from 'lucide-react';

export default function Navbar() {
  const location = useLocation();

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const onDashboard = isActive('/') && !location.pathname.startsWith('/eval') && !location.pathname.startsWith('/history');

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-brand">
          <div className="brand-icon">
            <Zap size={16} color="white" strokeWidth={2.5} />
          </div>
          <span>Hiring<span className="brand-gradient">Eval</span></span>
        </Link>

        <div className="navbar-links">
          <Link to="/" className={`nav-link ${onDashboard ? 'active' : ''}`}>
            <BarChart3 size={14} />
            Evaluate
          </Link>
          <Link to="/history" className={`nav-link ${isActive('/history') ? 'active' : ''}`}>
            <History size={14} />
            History
          </Link>
        </div>
      </div>
    </nav>
  );
}
