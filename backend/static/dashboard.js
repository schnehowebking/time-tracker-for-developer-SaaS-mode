async function postAction(url) {
  const res = await fetch(url, { method: "POST" });
  if (!res.ok) {
    alert("Request failed");
    return;
  }
  window.location.reload();
}

document.getElementById("startBtn")?.addEventListener("click", () => {
  postAction("/api/tracker/start");
});
document.getElementById("stopBtn")?.addEventListener("click", () => {
  postAction("/api/tracker/stop");
});

function renderDailyChart(data) {
  const root = document.getElementById("dailyChart");
  if (!root) return;
  const max = Math.max(...data.map((x) => x.tracked_seconds), 1);
  for (const row of data) {
    const bar = document.createElement("div");
    bar.className = "bar";
    bar.style.height = `${Math.max(8, (row.tracked_seconds / max) * 170)}px`;
    bar.title = `${row.day}: ${row.tracked_seconds}s`;
    root.appendChild(bar);
  }
}

renderDailyChart(window.__DAILY_DATA__ || []);
