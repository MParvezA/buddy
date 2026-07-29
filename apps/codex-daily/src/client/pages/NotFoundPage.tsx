import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="state-panel">
      <span className="state-symbol" aria-hidden="true">404</span>
      <h1>That local view does not exist</h1>
      <p>The daily dashboard and its representative data are still available.</p>
      <Link className="secondary-button link-button" to="/">Return to Today</Link>
    </div>
  );
}
