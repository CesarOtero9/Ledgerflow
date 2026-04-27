document.addEventListener("DOMContentLoaded", function () {
    const dateInput = document.getElementById("application_date");
    const monthPreview = document.getElementById("month_preview");
    const amountInput = document.getElementById("amount");

    const months = {
        1: "ENERO",
        2: "FEBRERO",
        3: "MARZO",
        4: "ABRIL",
        5: "MAYO",
        6: "JUNIO",
        7: "JULIO",
        8: "AGOSTO",
        9: "SEPTIEMBRE",
        10: "OCTUBRE",
        11: "NOVIEMBRE",
        12: "DICIEMBRE"
    };

    function initSelect2() {
        if (window.jQuery && $.fn.select2) {
            $(".select2-field").select2({
                width: "100%",
                placeholder: "Selecciona una opción",
                allowClear: true,
                language: {
                    noResults: function () {
                        return "Sin resultados";
                    },
                    searching: function () {
                        return "Buscando...";
                    }
                }
            });
        }
    }

    function updateMonthPreviewFromDMY(value) {
        const parts = value.split("/");

        if (parts.length !== 3) {
            monthPreview.value = "";
            return;
        }

        const day = parseInt(parts[0], 10);
        const month = parseInt(parts[1], 10);
        const year = parseInt(parts[2], 10);

        if (!day || !month || !year || month < 1 || month > 12) {
            monthPreview.value = "";
            return;
        }

        monthPreview.value = months[month] || "";
    }

    function formatCurrencyInput() {
        if (!amountInput) return;

        let value = amountInput.value;

        value = value.replace("$", "").replaceAll(",", "").replace("MXN", "").trim();

        if (value === "") {
            amountInput.value = "";
            return;
        }

        const numberValue = Number(value);

        if (isNaN(numberValue)) {
            return;
        }

        amountInput.value = numberValue.toLocaleString("es-MX", {
            style: "currency",
            currency: "MXN"
        });
    }

    initSelect2();

    if (dateInput && typeof flatpickr !== "undefined") {
        flatpickr(dateInput, {
            locale: "es",
            dateFormat: "d/m/Y",
            allowInput: true,
            defaultDate: dateInput.value ? dateInput.value : null,
            onChange: function (selectedDates, dateStr) {
                updateMonthPreviewFromDMY(dateStr);
            },
            onReady: function (_, dateStr) {
                if (dateStr) {
                    updateMonthPreviewFromDMY(dateStr);
                }
            }
        });

        dateInput.addEventListener("input", function () {
            updateMonthPreviewFromDMY(dateInput.value.trim());
        });

        if (dateInput.value) {
            updateMonthPreviewFromDMY(dateInput.value.trim());
        }
    }

    if (amountInput) {
        amountInput.addEventListener("blur", formatCurrencyInput);
    }
});