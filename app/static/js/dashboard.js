document.addEventListener("DOMContentLoaded", function () {
    const data = window.dashboardData || {};

    const ledgerPalette = [
        "#7AA997", "#496C70", "#98B57D", "#6C5E78", "#977A9A",
        "#1F4E78", "#31879B", "#BA6262", "#C77F7F", "#215967"
    ];

    const baseLayout = {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: { family: "Segoe UI, Aptos, Arial, sans-serif", color: "#26332E" },
        margin: { l: 45, r: 25, t: 28, b: 55 },
        transition: { duration: 700, easing: "cubic-in-out" }
    };

    const config = {
        responsive: true,
        displaylogo: false,
        scrollZoom: true,
        modeBarButtonsToRemove: ["select2d", "lasso2d", "autoScale2d"]
    };

    function money(value) {
        return `$${Number(value || 0).toLocaleString("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    }

    function hasValues(values) {
        return Array.isArray(values) && values.some(value => Number(value) > 0);
    }

    function safeArray(values) {
        return Array.isArray(values) ? values : [];
    }

    function renderEmptyChart(elementId, message) {
        const element = document.getElementById(elementId);
        if (!element) return;
        element.innerHTML = `
            <div class="empty-chart premium-empty">
                <div class="empty-orb"></div>
                <strong>Sin datos todavía</strong>
                <span>${message}</span>
            </div>
        `;
    }

    function getChartThemeColor(index) {
        return ledgerPalette[index % ledgerPalette.length];
    }

    function chartHeightForItems(count) {
        if (count <= 8) return 420;
        if (count <= 14) return 520;
        return 640;
    }

    function renderBudgetGaugeChart() {
        const summary = data.budgetSummary || {};
        const percentage = Number(summary.percentage || 0);
        if (!document.getElementById("budgetGaugeChart")) return;

        const gaugeColor = percentage >= 100 ? "#BA6262" : percentage >= 85 ? "#C77F7F" : percentage >= 60 ? "#98B57D" : "#7AA997";

        const trace = {
            type: "indicator",
            mode: "gauge+number+delta",
            value: percentage,
            delta: { reference: 100, increasing: { color: "#BA6262" }, decreasing: { color: "#7AA997" }, suffix: "% vs límite" },
            number: { suffix: "%", font: { size: 42, color: "#1F4E78" } },
            gauge: {
                shape: "angular",
                axis: { range: [0, Math.max(125, percentage)], tickwidth: 1, tickcolor: "rgba(73,108,112,0.35)" },
                bar: { color: gaugeColor, thickness: 0.30 },
                bgcolor: "rgba(255,255,255,0.42)",
                borderwidth: 0,
                steps: [
                    { range: [0, 60], color: "rgba(122,169,151,0.18)" },
                    { range: [60, 85], color: "rgba(152,181,125,0.22)" },
                    { range: [85, 100], color: "rgba(199,127,127,0.20)" },
                    { range: [100, Math.max(125, percentage)], color: "rgba(186,98,98,0.24)" }
                ],
                threshold: { line: { color: "#BA6262", width: 4 }, thickness: 0.78, value: 100 }
            },
            hovertemplate: "Cubierto: %{value}%<extra></extra>"
        };

        Plotly.newPlot("budgetGaugeChart", [trace], { ...baseLayout, margin: { l: 20, r: 20, t: 20, b: 20 } }, config);
    }

    function cuboidMesh(x0, x1, y0, y1, z0, z1, name, color, hoverText) {
        return {
            type: "mesh3d",
            name,
            x: [x0, x1, x1, x0, x0, x1, x1, x0],
            y: [y0, y0, y1, y1, y0, y0, y1, y1],
            z: [z0, z0, z0, z0, z1, z1, z1, z1],
            i: [0, 0, 0, 4, 4, 2, 1, 0, 3, 5, 6, 7],
            j: [1, 2, 3, 5, 6, 6, 5, 4, 7, 6, 7, 4],
            k: [2, 3, 0, 6, 7, 1, 0, 3, 4, 2, 3, 0],
            color,
            opacity: 0.92,
            flatshading: false,
            hovertemplate: `${hoverText}<extra>${name}</extra>`,
            lighting: { ambient: 0.58, diffuse: 0.72, specular: 0.55, roughness: 0.42, fresnel: 0.28 },
            lightposition: { x: 120, y: 80, z: 240 },
            showscale: false
        };
    }

    function renderBudgetComparisonChart() {
        const summary = data.budgetSummary || {};
        const budget = Number(summary.total_budget || 0);
        const paid = Number(summary.total_paid || 0);
        const directPaid = Number(summary.total_direct_paid || 0);
        const inheritedPaid = Math.max(Number(summary.total_inherited_paid || 0), paid - directPaid, 0);
        const remainingRaw = Number(summary.total_remaining || 0);
        const pending = remainingRaw < 0 ? 0 : remainingRaw;
        const exceeded = remainingRaw < 0 ? Math.abs(remainingRaw) : 0;

        if (!budget && !paid && !pending && !exceeded) {
            renderEmptyChart("budgetComparisonChart", "Asigna presupuestos y captura pagos para comparar.");
            return;
        }

        const maxValue = Math.max(budget, paid, pending, exceeded, 1);
        const traces = [];

        // 1) Presupuesto
        traces.push(cuboidMesh(
            -0.30, 0.30, -0.30, 0.30,
            0, Math.max(budget, maxValue * 0.012),
            "Presupuesto",
            "#1F4E78",
            `<b>Presupuesto</b><br>${money(budget)}`
        ));

        traces.push({
            type: "scatter3d",
            mode: "text",
            x: [0],
            y: [0],
            z: [Math.max(budget, maxValue * 0.012) + maxValue * 0.08],
            text: [`Presupuesto<br><b>${money(budget)}</b>`],
            textfont: { color: "#1F4E78", size: 12 },
            hoverinfo: "skip",
            showlegend: false
        });

        // 2) Pagado: se parte visualmente en pago directo + pago heredado de hijos.
        if (directPaid > 0) {
            traces.push(cuboidMesh(
                0.70, 1.30, -0.30, 0.30,
                0, directPaid,
                "Pago directo",
                "#31879B",
                `<b>Pago directo</b><br>${money(directPaid)}<br>Capturado exactamente en este nodo.`
            ));
        }

        if (inheritedPaid > 0) {
            traces.push(cuboidMesh(
                0.70, 1.30, -0.30, 0.30,
                directPaid, directPaid + inheritedPaid,
                "Pago de hijos",
                "#7AA997",
                `<b>Pago de hijos</b><br>${money(inheritedPaid)}<br>Acumulado desde nodos inferiores.`
            ));
        }

        if (paid === 0) {
            traces.push(cuboidMesh(
                0.70, 1.30, -0.30, 0.30,
                0, maxValue * 0.012,
                "Pagado",
                "rgba(122,169,151,0.35)",
                `<b>Pagado</b><br>${money(0)}`
            ));
        }

        traces.push({
            type: "scatter3d",
            mode: "text",
            x: [1],
            y: [0],
            z: [Math.max(paid, maxValue * 0.012) + maxValue * 0.08],
            text: [
                `Pagado<br><b>${money(paid)}</b><br>` +
                `Directo: ${money(directPaid)}<br>Hijos: ${money(inheritedPaid)}`
            ],
            textfont: { color: "#1F4E78", size: 11 },
            hoverinfo: "skip",
            showlegend: false
        });

        // 3) Pendiente / Excedido
        const thirdLabel = remainingRaw < 0 ? "Excedido" : "Pendiente";
        const thirdValue = remainingRaw < 0 ? exceeded : pending;
        traces.push(cuboidMesh(
            1.70, 2.30, -0.30, 0.30,
            0, Math.max(thirdValue, maxValue * 0.012),
            thirdLabel,
            remainingRaw < 0 ? "#BA6262" : "#98B57D",
            `<b>${thirdLabel}</b><br>${money(thirdValue)}`
        ));

        traces.push({
            type: "scatter3d",
            mode: "text",
            x: [2],
            y: [0],
            z: [Math.max(thirdValue, maxValue * 0.012) + maxValue * 0.08],
            text: [`${thirdLabel}<br><b>${money(thirdValue)}</b>`],
            textfont: { color: "#1F4E78", size: 12 },
            hoverinfo: "skip",
            showlegend: false
        });

        const layout = {
            ...baseLayout,
            showlegend: true,
            legend: { orientation: "h", y: 1.06, x: 0 },
            scene: {
                xaxis: {
                    title: "",
                    tickmode: "array",
                    tickvals: [0, 1, 2],
                    ticktext: ["Presupuesto", "Pagado", thirdLabel],
                    range: [-0.75, 2.75],
                    autorange: false,
                    backgroundcolor: "rgba(247,250,248,0.72)",
                    gridcolor: "rgba(73,108,112,0.16)",
                    zerolinecolor: "rgba(73,108,112,0.22)"
                },
                yaxis: {
                    title: "",
                    showticklabels: false,
                    range: [-0.58, 0.58],
                    autorange: false,
                    backgroundcolor: "rgba(247,250,248,0.72)",
                    gridcolor: "rgba(73,108,112,0.10)",
                    zerolinecolor: "rgba(73,108,112,0.12)"
                },
                zaxis: {
                    title: "Monto",
                    tickprefix: "$",
                    separatethousands: true,
                    range: [0, maxValue * 1.36],
                    autorange: false,
                    backgroundcolor: "rgba(247,250,248,0.72)",
                    gridcolor: "rgba(73,108,112,0.18)",
                    zerolinecolor: "rgba(73,108,112,0.16)"
                },
                camera: { eye: { x: 1.55, y: -1.80, z: 1.10 } },
                aspectratio: { x: 1.55, y: 0.55, z: 0.95 }
            },
            margin: { l: 0, r: 0, t: 8, b: 0 }
        };

        Plotly.newPlot("budgetComparisonChart", traces, layout, config);
    }

    function renderSubcategoryBudgetChart() {
        const chart = data.subcategoryBudgetChart || {};
        const labels = safeArray(chart.labels);
        const budgets = safeArray(chart.budgets).map(Number);
        const paids = safeArray(chart.paids).map(Number);
        const directPaids = safeArray(chart.direct_paids).map(Number);
        const inheritedPaids = safeArray(chart.inherited_paids).map(Number);
        const directCounts = safeArray(chart.direct_payment_counts).map(Number);
        const detailLabels = safeArray(chart.payment_detail_labels);
        const percentages = safeArray(chart.percentages).map(Number);

        if (!labels.length || (!hasValues(budgets) && !hasValues(paids))) {
            renderEmptyChart("subcategoryBudgetChart", "Asigna presupuestos a subrubros para ver su avance.");
            return;
        }

        const ordered = labels.map((label, i) => {
            const paid = paids[i] || 0;
            const direct = directPaids[i] || 0;
            const inherited = inheritedPaids[i] || Math.max(paid - direct, 0);
            return {
                label,
                budget: budgets[i] || 0,
                paid,
                direct,
                inherited,
                directCount: directCounts[i] || 0,
                detailLabel: detailLabels[i] || "Sin pagos",
                percentage: percentages[i] || 0
            };
        }).sort((a, b) => Math.max(b.budget, b.paid) - Math.max(a.budget, a.paid));

        const y = ordered.map(row => row.label).reverse();
        const budgetX = ordered.map(row => row.budget).reverse();
        const directX = ordered.map(row => row.direct).reverse();
        const inheritedX = ordered.map(row => row.inherited).reverse();
        const inheritedBase = ordered.map(row => row.direct).reverse();
        const pctText = ordered.map(row => `${row.percentage}%`).reverse();

        const custom = ordered.map(row => [
            money(row.budget),
            money(row.paid),
            money(row.direct),
            money(row.inherited),
            row.directCount,
            row.detailLabel,
            row.percentage
        ]).reverse();

        const budgetTrace = {
            x: budgetX,
            y,
            name: "Presupuesto efectivo",
            type: "bar",
            orientation: "h",
            marker: {
                color: "rgba(31,78,120,0.22)",
                line: { color: "rgba(31,78,120,0.55)", width: 1.5 }
            },
            customdata: custom,
            hovertemplate:
                "<b>%{y}</b><br>" +
                "Presupuesto efectivo: %{customdata[0]}<br>" +
                "Pagado total: %{customdata[1]}<br>" +
                "Tipo: %{customdata[5]}<extra></extra>"
        };

        const directTrace = {
            x: directX,
            y,
            name: "Pago directo",
            type: "bar",
            orientation: "h",
            marker: {
                color: "#31879B",
                line: { color: "rgba(255,255,255,0.88)", width: 1.5 }
            },
            text: directX.map((value, i) => value > 0 ? "Directo" : ""),
            textposition: "inside",
            insidetextanchor: "middle",
            customdata: custom,
            hovertemplate:
                "<b>%{y}</b><br>" +
                "Pago directo: %{customdata[2]}<br>" +
                "Movimientos directos: %{customdata[4]}<extra></extra>"
        };

        const inheritedTrace = {
            x: inheritedX,
            y,
            base: inheritedBase,
            name: "Pago de hijos",
            type: "bar",
            orientation: "h",
            marker: {
                color: "#7AA997",
                line: { color: "rgba(255,255,255,0.88)", width: 1.5 }
            },
            text: inheritedX.map(value => value > 0 ? "Hijos" : ""),
            textposition: "inside",
            insidetextanchor: "middle",
            customdata: custom,
            hovertemplate:
                "<b>%{y}</b><br>" +
                "Pago heredado desde hijos: %{customdata[3]}<br>" +
                "Pagado total: %{customdata[1]}<br>" +
                "Avance: %{customdata[6]}%<extra></extra>"
        };

        const pctTrace = {
            x: ordered.map(row => Math.max(row.budget, row.paid)).reverse(),
            y,
            mode: "text",
            type: "scatter",
            text: pctText,
            textposition: "middle right",
            textfont: { color: "#1F4E78", size: 12 },
            hoverinfo: "skip",
            showlegend: false
        };

        const height = chartHeightForItems(labels.length);
        const layout = {
            ...baseLayout,
            height,
            barmode: "overlay",
            bargap: 0.24,
            xaxis: {
                tickprefix: "$",
                separatethousands: true,
                gridcolor: "rgba(73,108,112,0.10)",
                zerolinecolor: "rgba(73,108,112,0.18)"
            },
            yaxis: {
                automargin: true,
                tickfont: { size: labels.length > 12 ? 10 : 12 }
            },
            legend: { orientation: "h", y: 1.08, x: 0 },
            annotations: chart.total_items > chart.displayed_items ? [{
                text: `Mostrando ${chart.displayed_items} de ${chart.total_items}. Los menores se agruparon, pero el detalle directo/heredado se conserva.`,
                x: 0, y: -0.18, xref: "paper", yref: "paper", showarrow: false,
                font: { size: 12, color: "#72827B" }, align: "left"
            }] : []
        };

        Plotly.newPlot("subcategoryBudgetChart", [budgetTrace, directTrace, inheritedTrace, pctTrace], layout, config);
    }

    function renderMonthlyChart() {
        const chart = data.monthlyChart || {};
        if (!chart.labels || !hasValues(chart.values)) {
            renderEmptyChart("monthlyChart", "Captura registros para ver la tendencia mensual.");
            return;
        }

        const trace = {
            x: chart.labels,
            y: chart.values,
            type: "scatter",
            mode: "lines+markers+text",
            fill: "tozeroy",
            fillcolor: "rgba(122, 169, 151, 0.18)",
            line: { width: 4, shape: "spline", color: "#31879B" },
            marker: { size: 10, color: "#7AA997", line: { color: "#1F4E78", width: 2 } },
            text: chart.values.map(v => money(v)),
            textposition: "top center",
            hovertemplate: "<b>%{x}</b><br>Monto: $%{y:,.2f}<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            xaxis: { tickangle: -25, gridcolor: "rgba(73,108,112,0.10)", zerolinecolor: "rgba(73,108,112,0.18)" },
            yaxis: { title: "Monto", tickprefix: "$", separatethousands: true, gridcolor: "rgba(73,108,112,0.10)", zerolinecolor: "rgba(73,108,112,0.18)" }
        };

        Plotly.newPlot("monthlyChart", [trace], layout, config);
    }

    function renderCategoryChart() {
        const chart = data.categoryChart || {};
        const labels = safeArray(chart.labels);
        const values = safeArray(chart.values).map(Number);
        const directPaids = safeArray(chart.direct_paids).map(Number);
        const inheritedPaids = safeArray(chart.inherited_paids).map(Number);
        const directCounts = safeArray(chart.direct_payment_counts).map(Number);
        const detailLabels = safeArray(chart.payment_detail_labels);
        const budgets = safeArray(chart.budgets).map(Number);
        const percentages = safeArray(chart.percentages).map(Number);

        if (!labels.length || !hasValues(values)) {
            renderEmptyChart("categoryChart", "Captura registros para ver totales por rubro.");
            return;
        }

        const ordered = labels.map((label, i) => {
            const value = values[i] || 0;
            const direct = directPaids[i] || 0;
            const inherited = inheritedPaids[i] || Math.max(value - direct, 0);
            return {
                label,
                value,
                direct,
                inherited,
                directCount: directCounts[i] || 0,
                detailLabel: detailLabels[i] || "Sin pagos",
                budget: budgets[i] || 0,
                percentage: percentages[i] || 0,
                color: getChartThemeColor(i)
            };
        }).filter(row => row.value > 0).sort((a, b) => b.value - a.value);

        if (!ordered.length) {
            renderEmptyChart("categoryChart", "Captura registros para ver totales por rubro.");
            return;
        }

        const total = ordered.reduce((acc, row) => acc + row.value, 0);
        const totalDirect = ordered.reduce((acc, row) => acc + row.direct, 0);
        const totalInherited = ordered.reduce((acc, row) => acc + row.inherited, 0);

        const donutLabels = ordered.map(row => row.label);
        const donutValues = ordered.map(row => row.value);
        const donutColors = ordered.map((_, i) => getChartThemeColor(i));

        const shadowTrace = {
            type: "pie",
            labels: donutLabels,
            values: donutValues,
            hole: 0.56,
            sort: false,
            direction: "clockwise",
            rotation: -35,
            marker: {
                colors: donutColors.map(() => "rgba(31, 78, 120, 0.23)"),
                line: { color: "rgba(31, 78, 120, 0.05)", width: 1 }
            },
            textinfo: "none",
            hoverinfo: "skip",
            showlegend: false,
            domain: { x: [0.025, 0.975], y: [0.00, 0.86] }
        };

        const mainTrace = {
            type: "pie",
            labels: donutLabels,
            values: donutValues,
            hole: 0.58,
            sort: false,
            direction: "clockwise",
            rotation: -35,
            marker: {
                colors: donutColors,
                line: { color: "rgba(255, 255, 255, 0.96)", width: 2.5 }
            },
            textinfo: "label+percent",
            textposition: "outside",
            textfont: { size: 11, color: "#26332E" },
            automargin: true,
            pull: ordered.map(row => row.direct > 0 ? 0.065 : 0.015),
            hovertemplate:
                "<b>%{label}</b><br>" +
                "Pagado total: %{customdata[0]}<br>" +
                "Pago directo: %{customdata[1]}<br>" +
                "Pago de hijos: %{customdata[2]}<br>" +
                "Movs. directos: %{customdata[3]}<br>" +
                "Tipo: %{customdata[4]}<br>" +
                "Presupuesto: %{customdata[5]}<br>" +
                "Avance: %{customdata[6]}%" +
                "<extra></extra>",
            customdata: ordered.map(row => [
                money(row.value),
                money(row.direct),
                money(row.inherited),
                row.directCount,
                row.detailLabel,
                money(row.budget),
                row.percentage
            ]),
            showlegend: false,
            domain: { x: [0.00, 1.00], y: [0.08, 0.98] }
        };

        const layout = {
            ...baseLayout,
            margin: { l: 10, r: 10, t: 18, b: 18 },
            showlegend: false,
            annotations: [
                {
                    text:
                        `<b>${money(total)}</b><br>` +
                        `<span style="font-size:11px;color:#72827B">Total pagado</span><br>` +
                        `<span style="font-size:10px;color:#31879B">Directo ${money(totalDirect)}</span><br>` +
                        `<span style="font-size:10px;color:#7AA997">Hijos ${money(totalInherited)}</span>`,
                    x: 0.5,
                    y: 0.52,
                    showarrow: false,
                    font: { size: 16, color: "#1F4E78" },
                    align: "center"
                },
                {
                    text: "Dona 3D · participación por rubro con pagos directos/heredados",
                    x: 0.5,
                    y: 1.05,
                    xref: "paper",
                    yref: "paper",
                    showarrow: false,
                    font: { size: 12, color: "#496C70" },
                    align: "center"
                },
                ...(chart.total_items > chart.displayed_items ? [{
                    text: `Top ${chart.displayed_items} de ${chart.total_items}; rubros menores agrupados.`,
                    x: 0,
                    y: -0.08,
                    xref: "paper",
                    yref: "paper",
                    showarrow: false,
                    font: { size: 11, color: "#72827B" },
                    align: "left"
                }] : [])
            ]
        };

        Plotly.newPlot("categoryChart", [shadowTrace, mainTrace], layout, config);
    }

    function renderSupplier3DChart() {
        const chart = data.supplier3dChart || {};
        if (!chart.suppliers || !hasValues(chart.totals)) {
            renderEmptyChart("supplier3dChart", "Captura registros para visualizar proveedores en 3D.");
            return;
        }

        const maxTotal = Math.max(...chart.totals.map(value => Number(value) || 0), 1);
        const markerSizes = chart.totals.map(value => Math.max(7, Math.min(28, 7 + ((Number(value) || 0) / maxTotal) * 22)));

        const trace = {
            x: chart.operations,
            y: chart.totals,
            z: chart.averages,
            text: chart.suppliers,
            type: "scatter3d",
            mode: "markers+text",
            textposition: "top center",
            marker: {
                size: markerSizes,
                color: chart.totals,
                colorscale: [[0, "#7AA997"], [0.25, "#98B57D"], [0.50, "#31879B"], [0.75, "#1F4E78"], [1, "#977A9A"]],
                opacity: 0.92,
                line: { color: "rgba(255,255,255,0.78)", width: 1 },
                colorbar: { title: "Total", tickprefix: "$", thickness: 12, len: 0.62 }
            },
            hovertemplate: "<b>%{text}</b><br>Operaciones: %{x}<br>Total: $%{y:,.2f}<br>Promedio: $%{z:,.2f}<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            scene: {
                xaxis: { title: "Operaciones", backgroundcolor: "rgba(247,250,248,0.72)", gridcolor: "rgba(73,108,112,0.18)" },
                yaxis: { title: "Total", tickprefix: "$", backgroundcolor: "rgba(247,250,248,0.72)", gridcolor: "rgba(73,108,112,0.18)" },
                zaxis: { title: "Promedio", tickprefix: "$", backgroundcolor: "rgba(247,250,248,0.72)", gridcolor: "rgba(73,108,112,0.18)" },
                camera: { eye: { x: 1.55, y: 1.75, z: 1.15 } }
            },
            margin: { l: 0, r: 0, t: 10, b: 0 }
        };

        Plotly.newPlot("supplier3dChart", [trace], layout, config);
    }

    function renderSurface3DChart() {
        const chart = data.surface3dChart || {};
        if (!chart.months || !chart.categories || !Array.isArray(chart.z) || chart.z.length === 0 || !chart.z.some(row => hasValues(row))) {
            renderEmptyChart("surface3dChart", "Captura registros en varios rubros y meses para crear el mapa 3D.");
            return;
        }

        const trace = {
            x: chart.months,
            y: chart.categories,
            z: chart.z,
            customdata: chart.customdata || undefined,
            type: "surface",
            colorscale: [[0, "#7AA997"], [0.18, "#98B57D"], [0.36, "#31879B"], [0.58, "#1F4E78"], [0.78, "#6C5E78"], [1, "#977A9A"]],
            opacity: 0.96,
            contours: { z: { show: true, usecolormap: true, highlightcolor: "#FFFFFF", project: { z: true } } },
            colorbar: { title: "Monto", tickprefix: "$", thickness: 13, len: 0.72 },
            hovertemplate:
                "<b>Mes:</b> %{x}<br>" +
                "<b>Rubro:</b> %{y}<br>" +
                "<b>Monto total:</b> $%{z:,.2f}<br>" +
                "<b>Pago directo:</b> $%{customdata[0]:,.2f}<br>" +
                "<b>Pago de hijos:</b> $%{customdata[1]:,.2f}" +
                "<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            scene: {
                xaxis: { title: "Mes", backgroundcolor: "rgba(247,250,248,0.72)", gridcolor: "rgba(73,108,112,0.18)", tickangle: -25 },
                yaxis: { title: "Rubro", backgroundcolor: "rgba(247,250,248,0.72)", gridcolor: "rgba(73,108,112,0.18)" },
                zaxis: { title: "Monto", tickprefix: "$", backgroundcolor: "rgba(247,250,248,0.72)", gridcolor: "rgba(73,108,112,0.18)" },
                camera: { eye: { x: 1.35, y: 1.75, z: 1.10 } }
            },
            margin: { l: 0, r: 0, t: 10, b: 0 }
        };

        Plotly.newPlot("surface3dChart", [trace], layout, config);
    }

    function animateNumbers() {
        document.querySelectorAll("[data-count-to]").forEach(el => {
            const finalValue = Number(el.getAttribute("data-count-to") || 0);
            const isMoney = el.getAttribute("data-money") === "1";
            const duration = 950;
            const start = performance.now();

            function tick(now) {
                const progress = Math.min((now - start) / duration, 1);
                const eased = 1 - Math.pow(1 - progress, 3);
                const value = finalValue * eased;
                el.textContent = isMoney ? money(value) : Math.round(value).toLocaleString("es-MX");
                if (progress < 1) requestAnimationFrame(tick);
            }
            requestAnimationFrame(tick);
        });
    }

    function initSelect2ForFilters() {
        if (window.jQuery && $.fn.select2) {
            $(".select2-field").select2({
                width: "100%",
                allowClear: true,
                placeholder: "Selecciona una opción",
                language: { noResults: () => "Sin resultados" }
            });
        }
    }

    function resizeChartsOnWindowChange() {
        const chartIds = ["budgetGaugeChart", "budgetComparisonChart", "subcategoryBudgetChart", "monthlyChart", "categoryChart", "supplier3dChart", "surface3dChart"];
        window.addEventListener("resize", function () {
            chartIds.forEach(id => {
                const element = document.getElementById(id);
                if (element && element.data) Plotly.Plots.resize(element);
            });
        });
    }

    initSelect2ForFilters();
    animateNumbers();
    renderBudgetGaugeChart();
    renderBudgetComparisonChart();
    renderSubcategoryBudgetChart();
    renderMonthlyChart();
    renderCategoryChart();
    renderSupplier3DChart();
    renderSurface3DChart();
    resizeChartsOnWindowChange();
});
