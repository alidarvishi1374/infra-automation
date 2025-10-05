// Dashboard JavaScript Module
document.addEventListener("DOMContentLoaded", function() {
    // Initialize dashboard
    loadAllData();
    
    // Auto-refresh every 30 seconds
    setInterval(loadAllData, 30000);
    
    // Search on Enter key
    $('#searchInput').keypress(function(e) {
        if (e.which === 13) { // Enter key
            loadAllData();
        }
    });
});

// Export dashboard to PDF (Professional version)
function exportToPDF() {
    showStatus('Generating PDF report...', 'success');
    
    const { jsPDF } = window.jspdf;
    const pdf = new jsPDF('p', 'mm', 'a4');
    
    // Date and time
    const now = new Date();
    const englishDate = now.toLocaleDateString('en-US');
    const time = now.toLocaleTimeString('en-US', { 
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
    
    const fileName = `s3-dashboard-report-${englishDate.replace(/\//g, '-')}-${time.replace(/:/g, '-')}.pdf`;

    // Beautiful header with gradient
    pdf.setFillColor(41, 128, 185);
    pdf.rect(0, 0, 210, 25, 'F');
    
    // Logo and title
    pdf.setTextColor(255, 255, 255);
    pdf.setFontSize(20);
    pdf.setFont('helvetica', 'bold');
    pdf.text('S3 DASHBOARD REPORT', 105, 15, { align: 'center' });
    
    // Date and time
    pdf.setFontSize(10);
    pdf.setFont('helvetica', 'normal');
    pdf.text(`Generated: ${englishDate} ${time}`, 105, 22, { align: 'center' });
    
    let yPosition = 40;

    // Overview statistics section with beautiful cards
    pdf.setFillColor(245, 245, 245);
    pdf.roundedRect(10, yPosition, 190, 30, 3, 3, 'F');
    
    pdf.setFontSize(16);
    pdf.setTextColor(44, 62, 80);
    pdf.setFont('helvetica', 'bold');
    pdf.text('OVERVIEW STATISTICS', 20, yPosition + 8);
    
    yPosition += 15;
    
    // Statistics in two columns
    pdf.setFontSize(11);
    pdf.setTextColor(0, 0, 0);
    pdf.setFont('helvetica', 'normal');
    
    // First column
    pdf.text(`• Buckets: ${$('#bucketCountValue').text()}`, 20, yPosition + 8);
    pdf.text(`• Total Size: ${$('#totalSizeValue').text()}`, 20, yPosition + 16);
    
    // Second column
    pdf.text(`• IAM Groups: ${$('#iamGroupsValue').text()}`, 110, yPosition + 8);
    pdf.text(`• IAM Users: ${$('#iamUsersValue').text()}`, 110, yPosition + 16);
    
    yPosition += 35;

    // Add charts as images
    const chartsPromises = [
        captureChart('barChart'),
        captureChart('pieChart'), 
        captureChart('objectCountChart')
    ];
    
    Promise.all(chartsPromises).then(chartImages => {
        const chartTitles = [
            'Bucket Sizes Distribution (Bar Chart)',
            'Bucket Sizes Percentage (Pie Chart)',
            'Number of Objects per Bucket'
        ];
        
        // Add each chart to PDF
        chartImages.forEach((chartData, index) => {
            if (chartData) {
                const chartWidth = 180;
                const chartHeight = (chartData.height * chartWidth) / chartData.width;
                
                // Check if there's enough space on the page
                if (yPosition + chartHeight + 20 > 270) {
                    pdf.addPage();
                    yPosition = 20;
                    
                    // Header for new pages
                    pdf.setFillColor(41, 128, 185);
                    pdf.rect(0, 0, 210, 15, 'F');
                    pdf.setTextColor(255, 255, 255);
                    pdf.setFontSize(12);
                    pdf.setFont('helvetica', 'bold');
                    pdf.text('S3 DASHBOARD REPORT - Continued', 105, 10, { align: 'center' });
                    yPosition = 25;
                }
                
                // Chart title
                pdf.setFontSize(14);
                pdf.setTextColor(44, 62, 80);
                pdf.setFont('helvetica', 'bold');
                pdf.text(chartTitles[index], 15, yPosition);
                yPosition += 8;
                
                // The chart itself
                pdf.addImage(chartData.dataUrl, 'PNG', 15, yPosition, chartWidth, chartHeight);
                yPosition += chartHeight + 15;
            }
        });
        
        // Add data table
        if (yPosition + 50 > 270) {
            pdf.addPage();
            yPosition = 25;
            
            // Header for new pages
            pdf.setFillColor(41, 128, 185);
            pdf.rect(0, 0, 210, 15, 'F');
            pdf.setTextColor(255, 255, 255);
            pdf.setFontSize(12);
            pdf.setFont('helvetica', 'bold');
            pdf.text('S3 DASHBOARD REPORT - Bucket Details', 105, 10, { align: 'center' });
        }
        
        // Table header
        pdf.setFillColor(52, 152, 219);
        pdf.roundedRect(10, yPosition, 190, 10, 2, 2, 'F');
        
        pdf.setTextColor(255, 255, 255);
        pdf.setFontSize(10);
        pdf.setFont('helvetica', 'bold');
        pdf.text('BUCKET DETAILS', 105, yPosition + 7, { align: 'center' });
        yPosition += 15;
        
        // Table column headers
        pdf.setFillColor(236, 240, 241);
        pdf.rect(10, yPosition, 190, 8, 'F');
        
        pdf.setTextColor(44, 62, 80);
        pdf.setFontSize(8);
        pdf.setFont('helvetica', 'bold');
        pdf.text('Bucket Name', 15, yPosition + 5);
        pdf.text('Size (Bytes)', 70, yPosition + 5);
        pdf.text('Size (GB)', 120, yPosition + 5);
        pdf.text('Objects', 170, yPosition + 5);
        
        yPosition += 10;
        
        // Get table data
        const tableData = [];
        $('#tableBody tr').each(function() {
            const row = [];
            $(this).find('td').each(function() {
                row.push($(this).text().trim());
            });
            tableData.push(row);
        });
        
        // Add table data to PDF
        pdf.setFontSize(7);
        pdf.setFont('helvetica', 'normal');
        pdf.setTextColor(0, 0, 0);
        
        tableData.forEach((row, rowIndex) => {
            if (yPosition > 270) {
                pdf.addPage();
                yPosition = 25;
                
                // Header for new pages
                pdf.setFillColor(41, 128, 185);
                pdf.rect(0, 0, 210, 15, 'F');
                pdf.setTextColor(255, 255, 255);
                pdf.setFontSize(12);
                pdf.setFont('helvetica', 'bold');
                pdf.text('S3 DASHBOARD REPORT - Bucket Details', 105, 10, { align: 'center' });
                
                // Table column headers again
                pdf.setFillColor(236, 240, 241);
                pdf.rect(10, yPosition, 190, 8, 'F');
                
                pdf.setTextColor(44, 62, 80);
                pdf.setFontSize(8);
                pdf.setFont('helvetica', 'bold');
                pdf.text('Bucket Name', 15, yPosition + 5);
                pdf.text('Size (Bytes)', 70, yPosition + 5);
                pdf.text('Size (GB)', 120, yPosition + 5);
                pdf.text('Objects', 170, yPosition + 5);
                
                yPosition += 10;
            }
            
            // Table rows with alternating colors
            if (rowIndex % 2 === 0) {
                pdf.setFillColor(250, 250, 250);
            } else {
                pdf.setFillColor(245, 245, 245);
            }
            pdf.rect(10, yPosition, 190, 5, 'F');
            
            pdf.setTextColor(0, 0, 0);
            pdf.text(row[0].substring(0, 25), 15, yPosition + 3.5); // Limit name length
            pdf.text(row[1], 70, yPosition + 3.5);
            pdf.text(row[2], 120, yPosition + 3.5);
            pdf.text(row[3], 170, yPosition + 3.5);
            
            yPosition += 5;
        });
        
        // Add beautiful footer
        const totalPages = pdf.internal.getNumberOfPages();
        for (let i = 1; i <= totalPages; i++) {
            pdf.setPage(i);
            
            // Separator line
            pdf.setDrawColor(200, 200, 200);
            pdf.line(10, 280, 200, 280);
            
            // Footer
            pdf.setFontSize(8);
            pdf.setTextColor(128, 128, 128);
            pdf.setFont('helvetica', 'normal');
            pdf.text('Generated by S3 Panel - AWS S3 Management Dashboard', 105, 285, { align: 'center' });
            pdf.text(`Page ${i} of ${totalPages}`, 105, 290, { align: 'center' });
        }
        
        // Download file with exact name
        pdf.save(fileName);
        showStatus('PDF report generated successfully!', 'success');
        
    }).catch(error => {
        console.error('Error generating PDF:', error);
        showStatus('Error generating PDF report', 'error');
    });
}

// Function to capture chart images (unchanged)
function captureChart(chartId) {
    return new Promise((resolve) => {
        const chartElement = document.getElementById(chartId);
        if (chartElement) {
            html2canvas(chartElement, {
                scale: 2,
                useCORS: true,
                backgroundColor: '#ffffff'
            }).then(canvas => {
                resolve({
                    dataUrl: canvas.toDataURL('image/png'),
                    width: canvas.width,
                    height: canvas.height
                });
            }).catch(() => resolve(null));
        } else {
            resolve(null);
        }
    });
}

// Show status message
function showStatus(message, type = 'success') {
    const statusEl = $('#statusMessage');
    statusEl.removeClass('status-success status-error')
           .addClass(type === 'success' ? 'status-success' : 'status-error')
           .text(message)
           .show();
    
    setTimeout(() => {
        statusEl.fadeOut();
    }, 5000);
}

// Load all data
function loadAllData() {
    const searchFilter = $('#searchInput').val().trim();
    loadOverviewStats(); // Update overall stats
    loadBucketData(searchFilter);
    loadObjectCountData(searchFilter);
}

// Load data without overview stats (for when only charts update)
function loadChartData() {
    const searchFilter = $('#searchInput').val().trim();
    loadBucketData(searchFilter);
    loadObjectCountData(searchFilter);
}

// Load overview stats (all statistics)
function loadOverviewStats() {
    $.getJSON('/api/overview-stats')  // Update this URL to match your Flask route
        .done(function(data) {
            updateOverviewStats(data);
        })
        .fail(function(xhr) {
            const errorMsg = xhr.responseJSON?.error || 'Error loading overview stats';
            showStatus(errorMsg, 'error');
        });
}

// Update overview cards with new data
function updateOverviewStats(data) {
    // Update bucket count card
    $('#bucketCountValue').text(data.bucket_count || 0);
    
    // Update total size card
    $('#totalSizeValue').text(data.total_size_mb ? data.total_size_mb.toFixed(2) + ' MB' : '0 MB');
    
    // Update IAM Groups card
    $('#iamGroupsValue').text(data.iam_groups_count || 0);
    
    // Update IAM Users card
    $('#iamUsersValue').text(data.iam_users_count || 0);
}

// Load bucket data (for size charts and table)
function loadBucketData(searchFilter = '') {
    $('#loadingTable').show();
    $('#dataTable').hide();
    
    $.getJSON('/api/bucket-data', { search: searchFilter })  // Update this URL to match your Flask route
        .done(function(data) {
            updateCharts(data);
            updateTable(data);
            $('#resultCount').text(data.length);
            
            // When charts are updated, update overall stats too
            loadOverviewStats();
        })
        .fail(function(xhr) {
            const errorMsg = xhr.responseJSON?.error || 'Error loading bucket data';
            $('#loadingTable').html('<div class="text-danger">Error: ' + errorMsg + '</div>');
            showStatus(errorMsg, 'error');
        });
}

// Load object count data
function loadObjectCountData(searchFilter = '') {
    $('#objectCountChart').html('<div class="loading">Loading object count data...</div>');
    
    $.getJSON('/api/object-count-data', { search: searchFilter })  // Update this URL to match your Flask route
        .done(function(data) {
            updateObjectCountChart(data);
        })
        .fail(function(xhr) {
            const errorMsg = xhr.responseJSON?.error || 'Error loading object count data';
            $('#objectCountChart').html('<div class="loading text-danger">Error: ' + errorMsg + '</div>');
            showStatus(errorMsg, 'error');
        });
}

// Update size charts with bucket data
function updateCharts(data) {
    if (data.length === 0) {
        $('#barChart').html('<div class="loading">No data available</div>');
        $('#pieChart').html('<div class="loading">No data available</div>');
        return;
    }
    
    const buckets = data.map(item => item.Bucket);
    const sizes = data.map(item => item.Size_GB);
    
    // Bar Chart for sizes
    const barTrace = {
        x: buckets,
        y: sizes,
        type: 'bar',
        marker: {
            color: buckets.map((_, i) => getColor(i))
        },
        text: sizes.map(size => size.toFixed(2) + ' GB'),
        textposition: 'auto',
        hovertemplate: '<b>%{x}</b><br>Size: %{y:.2f} GB<extra></extra>'
    };
    
    const barLayout = {
        title: 'Bucket Sizes Distribution',
        xaxis: { 
            title: 'Bucket',
            tickangle: -45,
            showgrid: false
        },
        yaxis: { 
            title: 'Size (GB)', 
            showgrid: true, 
            gridcolor: 'lightgray' 
        },
        plot_bgcolor: 'white',
        margin: { b: 100 }
    };
    
    $('#barChart').empty();
    Plotly.newPlot('barChart', [barTrace], barLayout);
    
    // Pie Chart for sizes
    const pieTrace = {
        labels: buckets,
        values: sizes,
        type: 'pie',
        hole: 0.4,
        marker: {
            colors: buckets.map((_, i) => getColor(i))
        },
        textinfo: 'label+percent',
        hovertemplate: '<b>%{label}</b><br>Size: %{value:.2f} GB<br>Percentage: %{percent}<extra></extra>'
    };
    
    const pieLayout = {
        title: 'Bucket Sizes Percentage',
        showlegend: true
    };
    
    $('#pieChart').empty();
    Plotly.newPlot('pieChart', [pieTrace], pieLayout);
}

// Update object count chart
function updateObjectCountChart(data) {
    if (data.length === 0) {
        $('#objectCountChart').html('<div class="loading">No object count data available</div>');
        return;
    }
    
    const buckets = data.map(item => item.Bucket);
    const objectCounts = data.map(item => item.Object_Count);
    
    // Bar Chart for object counts
    const barTrace = {
        x: buckets,
        y: objectCounts,
        type: 'bar',
        marker: {
            color: 'rgb(75, 192, 192)'
        },
        text: objectCounts.map(count => count.toLocaleString()),
        textposition: 'auto',
        hovertemplate: '<b>%{x}</b><br>Objects: %{y:,}<extra></extra>'
    };
    
    const layout = {
        title: 'Number of Objects per Bucket',
        xaxis: { 
            title: 'Bucket',
            tickangle: -45,
            showgrid: false
        },
        yaxis: { 
            title: 'Number of Objects',
            showgrid: true,
            gridcolor: 'lightgray'
        },
        plot_bgcolor: 'white',
        margin: { b: 100 }
    };
    
    $('#objectCountChart').empty();
    Plotly.newPlot('objectCountChart', [barTrace], layout);
}

// Update data table
function updateTable(data) {
    const tableBody = $('#tableBody');
    tableBody.empty();
    
    if (data.length === 0) {
        $('#loadingTable').html('<div class="text-center py-3">No buckets found</div>');
        return;
    }
    
    data.forEach(item => {
        const row = `<tr>
            <td><strong>${escapeHtml(item.Bucket)}</strong></td>
            <td>${formatNumber(item.Size_Bytes)}</td>
            <td>${item.Size_GB.toFixed(2)} GB</td>
            <td><span class="badge badge-primary">${formatNumber(item.Object_Count)}</span></td>
        </tr>`;
        tableBody.append(row);
    });
    
    $('#loadingTable').hide();
    $('#dataTable').show();
}

// Utility functions
function getColor(index) {
    const colors = [
        '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
        '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
        '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5',
        '#c49c94', '#f7b6d2', '#c7c7c7', '#dbdb8d', '#9edae5'
    ];
    return colors[index % colors.length];
}

function formatNumber(num) {
    return num.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function escapeHtml(unsafe) {
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}