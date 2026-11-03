interface ErrorStateProps {
  title: string;
  message: string;
  onRetry: () => void;
}

export function ErrorState({ title, message, onRetry }: ErrorStateProps) {
  return (
    <section className="error-state" role="alert" aria-live="assertive">
      <span className="error-icon" aria-hidden="true">
        !
      </span>
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
        <button className="retry-button" type="button" onClick={onRetry}>
          重试
        </button>
      </div>
    </section>
  );
}
