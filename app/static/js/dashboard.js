document.addEventListener("DOMContentLoaded", function () {
    const data = window.dashboardData || {};

    const ledgerPalette = [
        "#7AA997",
        "#496C70",
        "#98B57D",
        "#6C5E78",
        "#977A9A",
        "#1F4E78",
        "#31879B",
        "#BA6262",
        "#C77F7F"
    ];

    const baseLayout = {
        paper_bgcolor: "rgba(0,0,0,0)",
        plot_bgcolor: "rgba(0,0,0,0)",
        font: {
            family: "Segoe UI, Aptos, Arial, sans-serif",
            color: "#26332E"
        },
        margin: {
            l: 45,
            r: 25,
            t: 25,
            b: 55
        }
    };

    const config = {
        responsive: true,
        displaylogo: false,
        modeBarButtonsToRemove: [
            "select2d",
            "lasso2d",
            "autoScale2d"
        ]
    };

    function hasValues(values) {
        return Array.isArray(values) && values.some(value => Number(value) > 0);
    }

    function renderEmptyChart(elementId, message) {
        const element = document.getElementById(elementId);

        if (!element) {
            return;
        }

        element.innerHTML = `
            <div class="empty-chart">
                <div class="empty-orb"></div>
                <strong>Sin datos todavía</strong>
                <span>${message}</span>
            </div>
        `;
    }

    function renderBudgetGaugeChart() {
        const summary = data.budgetSummary || {};
        const percentage = Number(summary.percentage || 0);

        if (!document.getElementById("budgetGaugeChart")) {
            return;
        }

        const gaugeColor = percentage >= 100
            ? "#BA6262"
            : percentage >= 85
                ? "#C77F7F"
                : percentage >= 60
                    ? "#98B57D"
                    : "#7AA997";

        const trace = {
            type: "indicator",
            mode: "gauge+number",
            value: percentage,
            number: {
                suffix: "%",
                font: {
                    size: 42,
                    color: "#1F4E78"
                }
            },
            gauge: {
                axis: {
                    range: [0, Math.max(120, percentage)],
                    tickwidth: 1,
                    tickcolor: "rgba(73,108,112,0.35)"
                },
                bar: {
                    color: gaugeColor,
                    thickness: 0.28
                },
                bgcolor: "rgba(255,255,255,0.40)",
                borderwidth: 0,
                steps: [
                    { range: [0, 60], color: "rgba(122,169,151,0.18)" },
                    { range: [60, 85], color: "rgba(152,181,125,0.20)" },
                    { range: [85, 100], color: "rgba(199,127,127,0.20)" },
                    { range: [100, Math.max(120, percentage)], color: "rgba(186,98,98,0.24)" }
                ],
                threshold: {
                    line: {
                        color: "#BA6262",
                        width: 4
                    },
                    thickness: 0.75,
                    value: 100
                }
            },
            hovertemplate: "Cubierto: %{value}%<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            margin: {
                l: 20,
                r: 20,
                t: 20,
                b: 20
            }
        };

        Plotly.newPlot("budgetGaugeChart", [trace], layout, config);
    }

    function renderBudgetComparisonChart() {
        const summary = data.budgetSummary || {};
        const budget = Number(summary.total_budget || 0);
        const paid = Number(summary.total_paid || 0);
        const remaining = Number(summary.total_remaining || 0);

        if (!budget && !paid) {
            renderEmptyChart("budgetComparisonChart", "Asigna presupuestos y captura pagos para comparar.");
            return;
        }

        const trace = {
            x: ["Presupuesto", "Pagado", "Pendiente"],
            y: [budget, paid, remaining < 0 ? 0 : remaining],
            type: "bar",
            marker: {
                color: ["#1F4E78", "#31879B", "#7AA997"],
                line: {
                    color: "rgba(255,255,255,0.80)",
                    width: 2
                }
            },
            text: [
                `$${budget.toLocaleString("es-MX", { minimumFractionDigits: 2 })}`,
                `$${paid.toLocaleString("es-MX", { minimumFractionDigits: 2 })}`,
                `$${(remaining < 0 ? 0 : remaining).toLocaleString("es-MX", { minimumFractionDigits: 2 })}`
            ],
            textposition: "outside",
            hovertemplate: "<b>%{x}</b><br>Monto: $%{y:,.2f}<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            yaxis: {
                tickprefix: "$",
                separatethousands: true,
                gridcolor: "rgba(73,108,112,0.10)"
            },
            xaxis: {
                gridcolor: "rgba(73,108,112,0.10)"
            },
            margin: {
                l: 55,
                r: 20,
                t: 20,
                b: 50
            }
        };

        Plotly.newPlot("budgetComparisonChart", [trace], layout, config);
    }

    function renderSubcategoryBudgetChart() {
        const chart = data.subcategoryBudgetChart || {};

        if (!chart.labels || (!hasValues(chart.budgets) && !hasValues(chart.paids))) {
            renderEmptyChart("subcategoryBudgetChart", "Asigna presupuestos a subrubros para ver su avance.");
            return;
        }

        const budgetTrace = {
            x: chart.labels,
            y: chart.budgets,
            name: "Presupuesto",
            type: "bar",
            marker: {
                color: "#1F4E78"
            },
            hovertemplate: "<b>%{x}</b><br>Presupuesto: $%{y:,.2f}<extra></extra>"
        };

        const paidTrace = {
            x: chart.labels,
            y: chart.paids,
            name: "Pagado",
            type: "bar",
            marker: {
                color: "#7AA997"
            },
            hovertemplate: "<b>%{x}</b><br>Pagado: $%{y:,.2f}<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            barmode: "group",
            xaxis: {
                tickangle: -25,
                gridcolor: "rgba(73,108,112,0.10)"
            },
            yaxis: {
                tickprefix: "$",
                separatethousands: true,
                gridcolor: "rgba(73,108,112,0.10)"
            },
            legend: {
                orientation: "h",
                y: 1.12,
                x: 0
            }
        };

        Plotly.newPlot("subcategoryBudgetChart", [budgetTrace, paidTrace], layout, config);
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
            mode: "lines+markers",
            fill: "tozeroy",
            fillcolor: "rgba(122, 169, 151, 0.18)",
            line: {
                width: 4,
                shape: "spline",
                color: "#31879B"
            },
            marker: {
                size: 9,
                color: "#7AA997",
                line: {
                    color: "#1F4E78",
                    width: 2
                }
            },
            hovertemplate: "<b>%{x}</b><br>Monto: $%{y:,.2f}<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            xaxis: {
                title: "",
                tickangle: -25,
                gridcolor: "rgba(73,108,112,0.10)",
                zerolinecolor: "rgba(73,108,112,0.18)"
            },
            yaxis: {
                title: "Monto",
                tickprefix: "$",
                separatethousands: true,
                gridcolor: "rgba(73,108,112,0.10)",
                zerolinecolor: "rgba(73,108,112,0.18)"
            }
        };

        Plotly.newPlot("monthlyChart", [trace], layout, config);
    }

    function renderCategoryChart() {
        const chart = data.categoryChart || {};

        if (!chart.labels || !hasValues(chart.values)) {
            renderEmptyChart("categoryChart", "Captura registros para ver totales por rubro.");
            return;
        }

        const trace = {
            labels: chart.labels,
            values: chart.values,
            type: "pie",
            hole: 0.55,
            textinfo: "label+percent",
            marker: {
                colors: ledgerPalette,
                line: {
                    color: "rgba(255,255,255,0.88)",
                    width: 2
                }
            },
            hovertemplate: "<b>%{label}</b><br>Monto: $%{value:,.2f}<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            showlegend: false,
            margin: {
                l: 20,
                r: 20,
                t: 20,
                b: 20
            }
        };

        Plotly.newPlot("categoryChart", [trace], layout, config);
    }

    function renderSupplier3DChart() {
        const chart = data.supplier3dChart || {};

        if (!chart.suppliers || !hasValues(chart.totals)) {
            renderEmptyChart("supplier3dChart", "Captura registros para visualizar proveedores en 3D.");
            return;
        }

        const maxTotal = Math.max(...chart.totals.map(value => Number(value) || 0), 1);

        const markerSizes = chart.totals.map(value => {
            const safeValue = Number(value) || 0;
            const normalized = safeValue / maxTotal;
            return Math.max(6, Math.min(24, 6 + normalized * 20));
        });

        const markerColors = chart.totals.map(value => Number(value) || 0);

        const trace = {
            x: chart.operations,
            y: chart.totals,
            z: chart.averages,
            text: chart.suppliers,
            type: "scatter3d",
            mode: "markers",
            marker: {
                size: markerSizes,
                color: markerColors,
                colorscale: [
                    [0, "#7AA997"],
                    [0.25, "#98B57D"],
                    [0.50, "#31879B"],
                    [0.75, "#1F4E78"],
                    [1, "#977A9A"]
                ],
                opacity: 0.90,
                line: {
                    color: "rgba(255,255,255,0.70)",
                    width: 1
                },
                colorbar: {
                    title: "Total",
                    tickprefix: "$",
                    thickness: 12,
                    len: 0.62
                }
            },
            hovertemplate:
                "<b>%{text}</b><br>" +
                "Operaciones: %{x}<br>" +
                "Total: $%{y:,.2f}<br>" +
                "Promedio: $%{z:,.2f}" +
                "<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            scene: {
                xaxis: {
                    title: "Operaciones",
                    backgroundcolor: "rgba(247,250,248,0.72)",
                    gridcolor: "rgba(73,108,112,0.18)",
                    zerolinecolor: "rgba(73,108,112,0.22)"
                },
                yaxis: {
                    title: "Total",
                    tickprefix: "$",
                    backgroundcolor: "rgba(247,250,248,0.72)",
                    gridcolor: "rgba(73,108,112,0.18)",
                    zerolinecolor: "rgba(73,108,112,0.22)"
                },
                zaxis: {
                    title: "Promedio",
                    tickprefix: "$",
                    backgroundcolor: "rgba(247,250,248,0.72)",
                    gridcolor: "rgba(73,108,112,0.18)",
                    zerolinecolor: "rgba(73,108,112,0.22)"
                },
                camera: {
                    eye: {
                        x: 1.55,
                        y: 1.75,
                        z: 1.15
                    }
                }
            },
            margin: {
                l: 0,
                r: 0,
                t: 10,
                b: 0
            }
        };

        Plotly.newPlot("supplier3dChart", [trace], layout, config);
    }

    function renderSurface3DChart() {
        const chart = data.surface3dChart || {};

        if (
            !chart.months ||
            !chart.categories ||
            !Array.isArray(chart.z) ||
            chart.z.length === 0 ||
            !chart.z.some(row => hasValues(row))
        ) {
            renderEmptyChart("surface3dChart", "Captura registros en varios rubros y meses para crear el mapa 3D.");
            return;
        }

        const trace = {
            x: chart.months,
            y: chart.categories,
            z: chart.z,
            type: "surface",
            colorscale: [
                [0, "#7AA997"],
                [0.18, "#98B57D"],
                [0.36, "#31879B"],
                [0.58, "#1F4E78"],
                [0.78, "#6C5E78"],
                [1, "#977A9A"]
            ],
            opacity: 0.96,
            contours: {
                z: {
                    show: true,
                    usecolormap: true,
                    highlightcolor: "#FFFFFF",
                    project: {
                        z: true
                    }
                }
            },
            colorbar: {
                title: "Monto",
                tickprefix: "$",
                thickness: 13,
                len: 0.72
            },
            hovertemplate:
                "<b>Mes:</b> %{x}<br>" +
                "<b>Rubro:</b> %{y}<br>" +
                "<b>Monto:</b> $%{z:,.2f}" +
                "<extra></extra>"
        };

        const layout = {
            ...baseLayout,
            scene: {
                xaxis: {
                    title: "Mes",
                    backgroundcolor: "rgba(247,250,248,0.72)",
                    gridcolor: "rgba(73,108,112,0.18)",
                    zerolinecolor: "rgba(73,108,112,0.22)",
                    tickangle: -25
                },
                yaxis: {
                    title: "Rubro",
                    backgroundcolor: "rgba(247,250,248,0.72)",
                    gridcolor: "rgba(73,108,112,0.18)",
                    zerolinecolor: "rgba(73,108,112,0.22)"
                },
                zaxis: {
                    title: "Monto",
                    tickprefix: "$",
                    backgroundcolor: "rgba(247,250,248,0.72)",
                    gridcolor: "rgba(73,108,112,0.18)",
                    zerolinecolor: "rgba(73,108,112,0.22)"
                },
                camera: {
                    eye: {
                        x: 1.35,
                        y: 1.75,
                        z: 1.10
                    }
                }
            },
            margin: {
                l: 0,
                r: 0,
                t: 10,
                b: 0
            }
        };

        Plotly.newPlot("surface3dChart", [trace], layout, config);
    }

    function initSelect2ForFilters() {
        if (window.jQuery && $.fn.select2) {
            $(".select2-field").select2({
                width: "100%",
                allowClear: true,
                placeholder: "Selecciona una opción",
                language: {
                    noResults: function () {
                        return "Sin resultados";
                    }
                }
            });
        }
    }

    function resizeChartsOnWindowChange() {
        const chartIds = [
            "budgetGaugeChart",
            "budgetComparisonChart",
            "subcategoryBudgetChart",
            "monthlyChart",
            "categoryChart",
            "supplier3dChart",
            "surface3dChart"
        ];

        window.addEventListener("resize", function () {
            chartIds.forEach(id => {
                const element = document.getElementById(id);

                if (element && element.data) {
                    Plotly.Plots.resize(element);
                }
            });
        });
    }

    initSelect2ForFilters();

    renderBudgetGaugeChart();
    renderBudgetComparisonChart();
    renderSubcategoryBudgetChart();

    renderMonthlyChart();
    renderCategoryChart();
    renderSupplier3DChart();
    renderSurface3DChart();

    resizeChartsOnWindowChange();
});