// Sales dashboard: table with sort, filter, total and CSV export (see docs/README.md).
const state = { key: null, dir: 1, filter: "" };

function fmt(n) {
  return n.toLocaleString("ja-JP");
}

function dayOf(iso) {
  const d = new Date(iso);
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${d.getFullYear()}-${mm}-${dd}`;
}

function visibleRows() {
  const q = state.filter.trim();
  let rows = window.SALES.filter((r) => q === "" || r.name.includes(q) || r.region.includes(q));
  if (state.key) {
    const k = state.key;
    rows = rows.slice().sort((a, b) => {
      const x = String(a[k]), y = String(b[k]);
      if (x < y) return -state.dir;
      if (x > y) return state.dir;
      return a.id - b.id;
    });
  }
  return rows;
}

function render() {
  const rows = visibleRows();
  const tbody = document.querySelector("#tbl tbody");
  tbody.innerHTML = "";
  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${r.name}</td><td>${r.region}</td><td class="num">${fmt(r.amount)}</td><td>${dayOf(r.date)}</td>`;
    tbody.appendChild(tr);
  }
  const total = rows.reduce((s, r) => s + r.amount, 0);
  document.getElementById("sum").textContent = `合計: ${fmt(total)}円`;
}

function toCsv(rows) {
  const lines = ["name,region,amount,date"];
  for (const r of rows) lines.push([r.name, r.region, r.amount, dayOf(r.date)].join(","));
  return lines.join("\n");
}

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("#tbl th").forEach((th) => {
    th.addEventListener("click", () => {
      const k = th.dataset.key;
      state.dir = state.key === k ? -state.dir : 1;
      state.key = k;
      render();
    });
  });
  document.getElementById("filter").addEventListener("input", (e) => {
    state.filter = e.target.value;
    render();
  });
  render();
});

document.getElementById("export-btn").addEventListener("click", () => {
  document.getElementById("csv").value = toCsv(visibleRows());
});
