function init() {
  fetch("./graph.json")
    .then((r) => r.json())
    .then((graph) => {
      window.graphData = graph;
      buildUI(graph);
      buildGraph(graph);
    })
    .catch((e) => {
      document.getElementById("graph-container").innerHTML =
        '<p class="error">Failed to load graph.json: ' + e.message + "</p>";
    });
}

const CLASS_COLORS = {
  Person: "#4e79a7",
  Film: "#f28e2b",
  Organization: "#e15759",
  Location: "#76b7b2",
  Date: "#b07aa1",
};

const PREDICATE_COLORS = {
  DIRECTED: "#d62728",
  PRODUCED: "#9467bd",
  COMPOSED: "#8c564b",
  WROTE: "#e377c2",
  FOUNDED: "#7f7f7f",
  RELEASED_IN: "#bcbd22",
  WORKED_ON: "#17becf",
  RELATED_TO: "#aaaaaa",
};

const PREDICATE_DASH = {
  DIRECTED: null,
  PRODUCED: null,
  COMPOSED: null,
  WROTE: null,
  FOUNDED: null,
  RELEASED_IN: "4,2",
  WORKED_ON: "8,4",
  RELATED_TO: "2,4",
};

let svg, simulation, linkGroup, nodeGroup, labelGroup;
let selectedNode = null;

function buildUI(graph) {
  const cf = document.getElementById("class-filters");
  for (const c of graph.ontology.classes) {
    const lbl = document.createElement("label");
    lbl.innerHTML =
      '<input type="checkbox" class="class-filter" value="' +
      c +
      '" checked> <span style="color:' +
      CLASS_COLORS[c] +
      '">' +
      c +
      "</span>";
    cf.appendChild(lbl);
  }
  const pf = document.getElementById("predicate-filters");
  for (const p of graph.ontology.predicates) {
    const lbl = document.createElement("label");
    lbl.innerHTML =
      '<input type="checkbox" class="predicate-filter" value="' +
      p +
      '" checked> <span style="color:' +
      PREDICATE_COLORS[p] +
      '">' +
      p +
      "</span>";
    pf.appendChild(lbl);
  }

  document.querySelectorAll(".class-filter, .predicate-filter").forEach((cb) => {
    cb.addEventListener("change", () => updateVisibility());
  });

  document.getElementById("search").addEventListener("input", function () {
    const q = this.value.toLowerCase().trim();
    if (!q) {
      resetHighlight();
      return;
    }
    let found = null;
    if (window.graphData) {
      for (const n of window.graphData.nodes) {
        if (n.label.toLowerCase().includes(q)) {
          found = n;
          break;
        }
      }
    }
    if (found) {
      selectNode(found.id);
      centerOnNode(found.id);
      document.getElementById("search").style.borderColor = "#4e79a7";
    } else {
      document.getElementById("search").style.borderColor = "#e15759";
    }
  });

  document.getElementById("close-detail").addEventListener("click", () => {
    document.getElementById("detail-panel").classList.remove("open");
    resetHighlight();
  });

  document.getElementById("close-detail").style.display = "block";

  document.getElementById("detail-panel").addEventListener("click", function (e) {
    e.stopPropagation();
  });

  buildLegend(graph);
}

function buildLegend(graph) {
  const legend = document.getElementById("legend");
  let html = "<div class='legend-title'>Classes</div>";
  for (const c of graph.ontology.classes) {
    html +=
      '<div class="legend-item"><span class="legend-swatch" style="background:' +
      CLASS_COLORS[c] +
      '"></span> ' +
      c +
      "</div>";
  }
  html += "<div class='legend-title' style='margin-top:8px'>Predicates</div>";
  for (const p of graph.ontology.predicates) {
    html +=
      '<div class="legend-item"><span class="legend-swatch" style="background:' +
      PREDICATE_COLORS[p] +
      '"></span> ' +
      p +
      "</div>";
  }
  legend.innerHTML = html;
}

function buildGraph(graph) {
  const container = document.getElementById("graph-container");
  const W = container.clientWidth;
  const H = container.clientHeight;

  svg = d3
    .select("#graph")
    .attr("width", W)
    .attr("height", H)
    .attr("viewBox", [0, 0, W, H]);

  const gMain = svg.append("g");

  svg.call(
    d3.zoom().scaleExtent([0.1, 4]).on("zoom", (event) => {
      gMain.attr("transform", event.transform);
    })
  );

  const nodesData = graph.nodes.map((n) => ({ ...n }));
  const linksData = graph.links.map((l) => ({ ...l }));

  const nodeMap = new Map(nodesData.map((n) => [n.id, n]));
  for (const l of linksData) {
    l._s = l.source;
    l._t = l.target;
    l.source = nodeMap.get(l.source);
    l.target = nodeMap.get(l.target);
  }

  const rScale = d3
    .scaleSqrt()
    .domain([1, d3.max(nodesData, (d) => d.mentions) || 10])
    .range([3, 20]);

  simulation = d3
    .forceSimulation(nodesData)
    .force(
      "link",
      d3
        .forceLink(linksData)
        .id((d) => d.id)
        .distance(80)
    )
    .force("charge", d3.forceManyBody().strength(-200))
    .force("center", d3.forceCenter(W / 2, H / 2))
    .force("collide", d3.forceCollide().radius((d) => rScale(d.mentions) + 4));

  linkGroup = gMain
    .append("g")
    .attr("class", "links")
    .selectAll("line")
    .data(linksData)
    .join("line")
    .attr("stroke", (d) => PREDICATE_COLORS[d.predicate] || "#999")
    .attr("stroke-width", (d) => (d.predicate === "RELATED_TO" ? 0.5 : 1.5))
    .attr("stroke-dasharray", (d) => PREDICATE_DASH[d.predicate] || null)
    .attr("opacity", 0.6);

  linkGroup
    .append("title")
    .text(
      (d) =>
        d._s + " —" + d.predicate + "→ " + d._t + (d.sentence ? "\n" + d.sentence : "")
    );

  nodeGroup = gMain
    .append("g")
    .attr("class", "nodes")
    .selectAll("circle")
    .data(nodesData)
    .join("circle")
    .attr("r", (d) => rScale(d.mentions))
    .attr("fill", (d) => CLASS_COLORS[d.class] || "#999")
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.5)
    .attr("cursor", "pointer")
    .call(
      d3
        .drag()
        .on("start", dragStarted)
        .on("drag", dragged)
        .on("end", dragEnded)
    )
    .on("click", (event, d) => {
      event.stopPropagation();
      selectNode(d.id);
      centerOnNode(d.id);
    });

  nodeGroup.append("title").text((d) => d.label + " [" + d.class + "] (" + d.mentions + " mentions)");

  labelGroup = gMain
    .append("g")
    .attr("class", "labels")
    .selectAll("text")
    .data(nodesData)
    .join("text")
    .text((d) => d.label)
    .attr("font-size", (d) => Math.min(rScale(d.mentions) + 6, 14))
    .attr("dx", (d) => rScale(d.mentions) + 4)
    .attr("dy", 4)
    .attr("fill", "#ccc")
    .attr("pointer-events", "none");

  simulation.on("tick", () => {
    linkGroup
      .attr("x1", (d) => d.source.x)
      .attr("y1", (d) => d.source.y)
      .attr("x2", (d) => d.target.x)
      .attr("y2", (d) => d.target.y);

    nodeGroup.attr("cx", (d) => d.x).attr("cy", (d) => d.y);

    labelGroup.attr("x", (d) => d.x).attr("y", (d) => d.y);
  });

  svg.on("click", () => {
    resetHighlight();
    document.getElementById("detail-panel").classList.remove("open");
  });

  window.addEventListener("resize", () => {
    const w = container.clientWidth;
    const h = container.clientHeight;
    svg.attr("width", w).attr("height", h).attr("viewBox", [0, 0, w, h]);
    simulation.force("center", d3.forceCenter(w / 2, h / 2));
    simulation.alpha(0.3).restart();
  });
}

function dragStarted(event, d) {
  if (!event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x;
  d.fy = d.y;
}

function dragged(event, d) {
  d.fx = event.x;
  d.fy = event.y;
}

function dragEnded(event, d) {
  if (!event.active) simulation.alphaTarget(0);
  d.fx = null;
  d.fy = null;
}

function selectNode(nodeId) {
  selectedNode = nodeId;
  const graph = window.graphData;
  if (!graph) return;

  const neighborLinks = graph.links.filter(
    (l) => l.source === nodeId || l.target === nodeId
  );
  const neighborIds = new Set();
  for (const l of neighborLinks) {
    const other = l.source === nodeId ? l.target : l.source;
    neighborIds.add(other);
  }
  neighborIds.add(nodeId);

  nodeGroup.attr("opacity", (d) => (neighborIds.has(d.id) ? 1 : 0.1));
  linkGroup.attr("opacity", (d) =>
    d._s === nodeId || d._t === nodeId ? 1 : 0.05
  );
  labelGroup.attr("opacity", (d) => (neighborIds.has(d.id) ? 1 : 0));

  const node = graph.nodes.find((n) => n.id === nodeId);
  if (!node) return;

  let html =
    "<h2>" +
    node.label +
    "</h2>" +
    "<p><strong>Class:</strong> " +
    node.class +
    "</p>" +
    "<p><strong>Mentions:</strong> " +
    node.mentions +
    "</p>" +
    "<h3>Relationships</h3>";

  if (neighborLinks.length === 0) {
    html += "<p>No relationships found.</p>";
  } else {
    html += '<ul class="rel-list">';
    for (const l of neighborLinks) {
      const otherId = l.source === nodeId ? l.target : l.source;
      const otherNode = graph.nodes.find((n) => n.id === otherId);
      const otherLabel = otherNode ? otherNode.label : otherId;
      const dir = l.source === nodeId ? "→" : "←";
      html +=
        "<li>" +
        '<span class="pred-tag" style="background:' +
        PREDICATE_COLORS[l.predicate] +
        '">' +
        l.predicate +
        "</span> " +
        " " +
        dir +
        " <strong>" +
        otherLabel +
        "</strong>" +
        (l.sentence
          ? '<p class="sentence">"' + l.sentence + '"</p>'
          : "") +
        "</li>";
    }
    html += "</ul>";
  }
  document.getElementById("detail-content").innerHTML = html;
  document.getElementById("detail-panel").classList.add("open");
}

function centerOnNode(nodeId) {
  const node = nodeGroup.filter((d) => d.id === nodeId).node();
  if (!node) return;
  const cx = node.cx.baseVal.value;
  const cy = node.cy.baseVal.value;
  const W = document.getElementById("graph-container").clientWidth;
  const H = document.getElementById("graph-container").clientHeight;
  const transform = d3.zoomIdentity.translate(W / 2 - cx, H / 2 - cy).scale(1.5);
  svg.transition().duration(500).call(d3.zoom().transform, transform);
}

function resetHighlight() {
  selectedNode = null;
  nodeGroup.attr("opacity", 1);
  linkGroup.attr("opacity", 0.6);
  labelGroup.attr("opacity", 1);
}

function updateVisibility() {
  const checkedClasses = new Set();
  document
    .querySelectorAll(".class-filter:checked")
    .forEach((cb) => checkedClasses.add(cb.value));
  const checkedPreds = new Set();
  document
    .querySelectorAll(".predicate-filter:checked")
    .forEach((cb) => checkedPreds.add(cb.value));

  nodeGroup.attr("display", (d) =>
    checkedClasses.has(d.class) ? null : "none"
  );

  linkGroup.attr("display", (d) => {
    const sOk = nodeGroup.filter((n) => n.id === d._s).attr("display") !== "none";
    const tOk = nodeGroup.filter((n) => n.id === d._t).attr("display") !== "none";
    return sOk && tOk && checkedPreds.has(d.predicate) ? null : "none";
  });

  labelGroup.attr("display", (d) =>
    checkedClasses.has(d.class) ? null : "none"
  );
}

init();
