/* Shared chrome for the catpart-parser Pages site: nav, footer, helpers.
   Each page carries <nav data-page="index|format|viewer|gallery|evidence|grind"></nav>
   and a <footer data-common></footer> placeholder. */
(function () {
  var PAGES = [
    ["index", "Home", "index.html"],
    ["format", "Format docs", "format.html"],
    ["viewer", "Viewer", "viewer.html"],
    ["gallery", "Gallery", "gallery.html"],
    ["evidence", "Evidence", "evidence.html"],
    ["grind", "The grind", "grind.html"],
    ["repo", "GitHub", "https://github.com/MadManJohnSmith/catpart-parser"],
  ];
  var current = document.querySelector("nav[data-page]");
  var here = current ? current.getAttribute("data-page") : "index";
  var links = PAGES.map(function (p) {
    var cls = p[0] === here ? ' class="active"' : "";
    return '<a' + cls + ' href="' + p[2] + '">' + p[1] + "</a>";
  }).join("");
  if (current) {
    current.innerHTML =
      '<div class="logo">' +
      '<svg viewBox="0 0 32 32" fill="none"><rect width="32" height="32" rx="7" fill="#101a2e"/>' +
      '<path d="M22 10a8 8 0 1 0 0 12" stroke="#38e1ff" stroke-width="3.5" stroke-linecap="round"/></svg>' +
      "catpart-parser</div>" +
      '<div class="links">' + links + "</div>";
  }
  var footer = document.querySelector("footer[data-common]");
  if (footer) {
    footer.innerHTML =
      "Open-source CATIA V5 parsing, measured on a public 1,824-file corpus. Fitness published " +
      "locally by <code>scripts/publish_fitness.py</code> (ADR-0003); the README badge stays L1 " +
      "(ADR-0001). Every figure on this site mirrors committed evidence or an accepted run — " +
      '<a href="https://github.com/MadManJohnSmith/catpart-parser/tree/main/docs/evidence">browse the evidence</a>.';
  }
})();
