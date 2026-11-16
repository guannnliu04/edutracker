import katex from "katex";
import "katex/dist/katex.min.css";

/** 把含 $...$ 的字串渲染成文字+公式(內容皆為自家題庫,非使用者輸入) */
export function MathText({ text }: { text: string }) {
  const parts = text.split("$");
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <span
            key={i}
            dangerouslySetInnerHTML={{
              __html: katex.renderToString(part, { throwOnError: false, output: "html" }),
            }}
          />
        ) : (
          <span key={i}>{part}</span>
        ),
      )}
    </>
  );
}
