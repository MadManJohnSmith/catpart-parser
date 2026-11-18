/* Minimal markdown renderer for the format-docs portal — the subset the
   committed docs/format/*.md files use: #/##/###/#### headings, fenced code,
   pipe tables, lists (two levels), blockquotes, hr, and inline code/bold/
   italic/links. HTML in the source is escaped, never interpreted. */
(function () {
  "use strict";

  function esc(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  function inline(s) {
    var out = esc(s);
    out = out.replace(/`([^`]+)`/g, "<code>$1</code>");
    out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    out = out.replace(/\*([^*]+)\*/g, "<em>$1</em>");
    out = out.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '<a href="$2">$1</a>');
    return out;
  }

  function renderMarkdown(text) {
    var lines = text.replace(/\r\n/g, "\n").split("\n");
    var html = [];
    var i = 0;
    while (i < lines.length) {
      var line = lines[i];

      if (/^\s*```/.test(line)) {
        var lang = line.replace(/^\s*```/, "").trim();
        var buf = [];
        i++;
        while (i < lines.length && !/^\s*```/.test(lines[i])) {
          buf.push(lines[i]);
          i++;
        }
        i++; // closing fence (or EOF)
        html.push(
          '<pre class="md-code">' +
            (lang ? '<span class="lang">' + esc(lang) + "</span>" : "") +
            "<code>" +
            esc(buf.join("\n")) +
            "</code></pre>"
        );
        continue;
      }

      var h = line.match(/^(#{1,4})\s+(.*)$/);
      if (h) {
        var level = h[1].length;
        html.push("<h" + level + ">" + inline(h[2]) + "</h" + level + ">");
        i++;
        continue;
      }

      if (/^\s*(---+|\*\*\*+)\s*$/.test(line)) {
        html.push("<hr>");
        i++;
        continue;
      }

      if (/^\s*\|/.test(line) && i + 1 < lines.length && /^\s*\|[\s:|-]+\|?\s*$/.test(lines[i + 1])) {
        var cells = function (row) {
          return row.trim().replace(/^\|/, "").replace(/\|$/, "").split("|");
        };
        var head = cells(line);
        i += 2;
        var body = [];
        while (i < lines.length && /^\s*\|/.test(lines[i])) {
          body.push(cells(lines[i]));
          i++;
        }
        html.push(
          "<table><thead><tr>" +
            head.map(function (c) { return "<th>" + inline(c.trim()) + "</th>"; }).join("") +
            "</tr></thead><tbody>" +
            body
              .map(function (r) {
                return "<tr>" + head.map(function (_, k) { return "<td>" + inline((r[k] || "").trim()) + "</td>"; }).join("") + "</tr>";
              })
              .join("") +
            "</tbody></table>"
        );
        continue;
      }

      if (/^\s*([-*+]\s|\d+\.\s)/.test(line)) {
        var ordered = /^\s*\d+\./.test(line);
        var items = [];
        while (i < lines.length && /^\s*([-*+]\s|\d+\.\s)/.test(lines[i])) {
          var indent = (lines[i].match(/^\s*/) || [""])[0].length;
          var content = lines[i].replace(/^\s*([-*+]|\d+\.)\s+/, "");
          var sub = indent >= 2 ? " class='md-sub'" : "";
          items.push("<li" + sub + ">" + inline(content) + "</li>");
          i++;
        }
        var tag = ordered ? "ol" : "ul";
        html.push("<" + tag + ">" + items.join("") + "</" + tag + ">");
        continue;
      }

      if (/^\s*>\s?/.test(line)) {
        var quote = [];
        while (i < lines.length && /^\s*>\s?/.test(lines[i])) {
          quote.push(lines[i].replace(/^\s*>\s?/, ""));
          i++;
        }
        html.push("<blockquote>" + inline(quote.join(" ")) + "</blockquote>");
        continue;
      }

      if (!line.trim()) {
        i++;
        continue;
      }

      var para = [];
      while (i < lines.length && lines[i].trim() && !/^\s*(#{1,4}\s|```|\||[-*+]\s|\d+\.\s|>)/.test(lines[i])) {
        para.push(lines[i].trim());
        i++;
      }
      html.push("<p>" + inline(para.join(" ")) + "</p>");
    }
    return html.join("\n");
  }

  var api = { renderMarkdown: renderMarkdown, inline: inline };
  /* global module, window */
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api; // node (smoke tests)
  } else if (typeof window !== "undefined") {
    window.MD = api; // browser
  }
})();
