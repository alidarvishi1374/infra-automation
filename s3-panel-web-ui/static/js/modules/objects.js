    $(document).ready(function(){
        // FLASH DISMISS
        setTimeout(function(){ $('.alert').fadeOut(600, function(){ $(this).remove(); }); }, 4000);

        // -------------------------
        // Objects table pagination + search
        // -------------------------
        const $table = $("#objectTable");
        let $rows = $table.find("tbody tr");
        const $pagination = $("#pagination");
        const $rowsPerPageSelect = $("#rowsPerPageSelect");
        let currentPage = 1;
        let rowsPerPage = parseInt($rowsPerPageSelect.val() || 10);

        function renderTable(filteredRows){
            filteredRows = filteredRows || $rows.filter(function(){ return $(this).is(':visible') || true; });
            // if filteredRows is jQuery set from search, use it; otherwise use all rows
            if(filteredRows.length === 0 && $rows.length > 0){
                // nothing matched — hide all and render empty pagination
                $rows.hide();
                renderPagination(filteredRows);
                return;
            }
            const start = (currentPage-1)*rowsPerPage;
            const end = start + rowsPerPage;
            $rows.hide();
            filteredRows.slice(start, end).show();
            renderPagination(filteredRows);
        }

        function renderPagination(filteredRows){
            filteredRows = filteredRows || $rows;
            const totalPages = Math.max(1, Math.ceil(filteredRows.length / rowsPerPage));
            $pagination.empty();

            const prevLi = $('<li class="page-item"></li>');
            if(currentPage===1) prevLi.addClass("disabled");
            const prevA = $('<a class="page-link" href="#">«</a>');
            prevA.click(function(e){ e.preventDefault(); if(currentPage>1){ currentPage--; renderTable(filteredRows); }});
            prevLi.append(prevA); $pagination.append(prevLi);

            for(let i=1;i<=totalPages;i++){
                const li = $('<li class="page-item"></li>');
                if(i===currentPage) li.addClass("active");
                const a = $('<a class="page-link" href="#">'+i+'</a>');
                a.click(function(e){ e.preventDefault(); currentPage=i; renderTable(filteredRows); });
                li.append(a); $pagination.append(li);
            }

            const nextLi = $('<li class="page-item"></li>');
            if(currentPage===totalPages) nextLi.addClass("disabled");
            const nextA = $('<a class="page-link" href="#">»</a>');
            nextA.click(function(e){ e.preventDefault(); if(currentPage<totalPages){ currentPage++; renderTable(filteredRows); }});
            nextLi.append(nextA); $pagination.append(nextLi);
        }

        renderTable($rows);

        $rowsPerPageSelect.change(function(){
            rowsPerPage = parseInt($(this).val());
            currentPage = 1;
            // if a search/filter is active, use filtered rows
            const val = $("#searchInput").val();
            if(val && val.length){
                const $filteredRows = $rows.filter(function(){ return $(this).text().toLowerCase().indexOf(val.toLowerCase()) > -1; });
                renderTable($filteredRows);
            } else {
                renderTable($rows);
            }
        });

        $("#searchInput").on("keyup", function(){
            const val = $(this).val().toLowerCase();
            const $filteredRows = $rows.filter(function(){ return $(this).text().toLowerCase().indexOf(val) > -1; });
            currentPage = 1;
            renderTable($filteredRows);
        });

        // -------------------------
        // Buckets cards pagination + search
        // -------------------------
        const $buckets = $("#bucketList > div");
        const $bucketsPerPageSelect = $("#bucketsPerPageSelect");
        const $bucketsPagination = $("#bucketsPagination");
        let currentBucketPage = 1;
        let bucketsPerPage = parseInt($bucketsPerPageSelect.val() || 10);

        function renderBuckets(filtered){
            filtered = filtered || $buckets;
            const start = (currentBucketPage-1)*bucketsPerPage;
            const end = start + bucketsPerPage;
            $buckets.hide();
            filtered.hide().slice(start, end).show();
            renderBucketsPagination(filtered);
        }

        function renderBucketsPagination(filtered){
            filtered = filtered || $buckets;
            const totalPages = Math.max(1, Math.ceil(filtered.length / bucketsPerPage));
            $bucketsPagination.empty();

            const prevLi = $('<li class="page-item"></li>');
            if(currentBucketPage === 1) prevLi.addClass("disabled");
            const prevA = $('<a class="page-link" href="#">«</a>');
            prevA.click(function(e){ e.preventDefault(); if(currentBucketPage > 1){ currentBucketPage--; renderBuckets(filtered); }});
            prevLi.append(prevA); $bucketsPagination.append(prevLi);

            for(let i=1;i<=totalPages;i++){
                const li = $('<li class="page-item"></li>');
                if(i===currentBucketPage) li.addClass("active");
                const a = $('<a class="page-link" href="#">'+i+'</a>');
                a.click(function(e){ e.preventDefault(); currentBucketPage=i; renderBuckets(filtered); });
                li.append(a); $bucketsPagination.append(li);
            }

            const nextLi = $('<li class="page-item"></li>');
            if(currentBucketPage === totalPages) nextLi.addClass("disabled");
            const nextA = $('<a class="page-link" href="#">»</a>');
            nextA.click(function(e){ e.preventDefault(); if(currentBucketPage < totalPages){ currentBucketPage++; renderBuckets(filtered); }});
            nextLi.append(nextA); $bucketsPagination.append(nextLi);
        }

        renderBuckets();

        $bucketsPerPageSelect.change(function(){
            bucketsPerPage = parseInt($(this).val());
            currentBucketPage = 1;
            renderBuckets();
        });

        $("#bucketSearchInput").on("keyup", function(){
            const val = $(this).val().toLowerCase();
            const $filteredBuckets = $buckets.filter(function(){
                const name = $(this).find("h6.card-title").text().toLowerCase();
                return name.indexOf(val) > -1;
            });
            currentBucketPage = 1;
            renderBuckets($filteredBuckets);
        });

        // -------------------------
        // Upload modal logic (Bootstrap 4: use .modal())
        // -------------------------
        $("#uploadBtn").click(function(){
            const fileInput = $("#fileInput")[0];
            const folderInput = $('input[name="folder"]').val();

            if(!fileInput || !fileInput.files || !fileInput.files.length){
                $("#customAlert").text("Please select a file before uploading.").removeClass("d-none").addClass("show");
                return;
            }

            $("#customAlert").addClass("d-none").removeClass("show");
            $("#uploadFileName").text(fileInput.files[0].name);
            $("#uploadTargetPath").text(folderInput || "/");
            $("#uploadConfirmModal").modal("show");
        });

        $("#confirmUploadBtn").click(function(){
            $("#uploadForm").submit();
        });

        // -------------------------
        // Delete modal logic
        // -------------------------
        let deleteForm = null;
        $(".deleteBtn").on("click", function(){
            deleteForm = $(this).closest(".delete-form");
            $("#deleteFileName").text(deleteForm.data("key"));
            $("#deleteFilePath").text(deleteForm.data("prefix") || "/");
            $("#deleteModal").modal("show");
        });

        $("#confirmDeleteBtn").click(function(){
            if(deleteForm) deleteForm.submit();
        });

    });