import { useSearchParams } from "react-router-dom";
import { useTitle } from "../lib/useTitle";

/**
 * Static-site feedback: posts to FormSubmit, which forwards to email.
 * No backend, honeypot field for bots, redirect back here with ?sent=1.
 */
export default function Feedback() {
  useTitle("Feedback · Over Expected");
  const [params] = useSearchParams();
  const sent = params.get("sent") === "1";

  return (
    <div className="mx-auto max-w-xl px-5 py-12 sm:px-8 sm:py-16">
      <h1 className="font-display text-3xl font-bold tracking-tight text-ink sm:text-5xl">
        Feedback
      </h1>
      <p className="mt-3 text-sm leading-relaxed text-ink-soft sm:text-base">
        Spotted something off, want a feature, or disagree with the method?
        It lands directly in my inbox.
      </p>

      {sent ? (
        <div className="mt-10 rounded-md border border-line bg-wash px-5 py-6">
          <p className="font-display text-lg font-semibold text-ink">
            Sent. Thank you.
          </p>
          <p className="mt-1 text-sm text-ink-soft">
            If it needs a reply and you left an email, you'll get one.
          </p>
        </div>
      ) : (
        <form
          action="https://formsubmit.co/kevinkrajnc@gmail.com"
          method="POST"
          className="mt-10 flex flex-col gap-5"
        >
          <input type="hidden" name="_subject" value="Over Expected feedback" />
          <input type="hidden" name="_captcha" value="false" />
          <input
            type="hidden"
            name="_next"
            value="https://over-expected.vercel.app/feedback?sent=1"
          />
          <input
            type="text"
            name="_honey"
            tabIndex={-1}
            autoComplete="off"
            className="hidden"
            aria-hidden="true"
          />
          <label className="flex flex-col gap-1.5">
            <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
              Name <span className="normal-case">(optional)</span>
            </span>
            <input
              type="text"
              name="name"
              className="rounded-md border border-line bg-paper px-3 py-2.5 font-display text-[14px] text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-ink"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
              Email <span className="normal-case">(optional, for a reply)</span>
            </span>
            <input
              type="email"
              name="email"
              className="rounded-md border border-line bg-paper px-3 py-2.5 font-display text-[14px] text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-ink"
            />
          </label>
          <label className="flex flex-col gap-1.5">
            <span className="font-display text-[11px] font-medium uppercase tracking-wider text-ink-faint">
              Message
            </span>
            <textarea
              name="message"
              required
              rows={6}
              className="rounded-md border border-line bg-paper px-3 py-2.5 font-serif text-[15px] text-ink placeholder:text-ink-faint focus:border-ink-faint focus:outline-none focus-visible:outline-2 focus-visible:-outline-offset-1 focus-visible:outline-ink"
            />
          </label>
          <button
            type="submit"
            className="self-start rounded-md bg-ink px-5 py-2.5 font-display text-sm font-medium text-paper transition-[opacity,transform] duration-150 hover:opacity-85 active:scale-[0.98] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink"
          >
            Send feedback
          </button>
          <p className="text-xs text-ink-faint">
            Or email{" "}
            <a
              href="mailto:kevinkrajnc@gmail.com"
              className="underline underline-offset-2 hover:text-ink"
            >
              kevinkrajnc@gmail.com
            </a>{" "}
            directly.
          </p>
        </form>
      )}
    </div>
  );
}
