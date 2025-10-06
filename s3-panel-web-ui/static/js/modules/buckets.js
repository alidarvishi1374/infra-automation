$(document).ready(function() {
    const table = $('#bucketsTable').DataTable({
        "paging": true,
        "pageLength": 10,
        "lengthChange": true,
        "searching": true,
        "ordering": true,
        "info": true,
        "autoWidth": false,
        "responsive": true,
        "language": {
            "paginate": {
                "previous": "‹",
                "next": "›"
            },
            "search": "Search:",
            "lengthMenu": "Show _MENU_ entries",
            "info": "Showing _START_ to _END_ of _TOTAL_ entries",
            "infoEmpty": "Showing 0 to 0 of 0 entries",
            "infoFiltered": "(filtered from _MAX_ total entries)",
            "emptyTable": "No data available in table",
            "zeroRecords": "No matching records found",
            "loadingRecords": "Loading...",
            "processing": "Processing..."
        },
        "columnDefs": [
            {
                "targets": [4], 
                "type": "num",
                "render": function(data, type, row) {
                    if (type === 'sort' || type === 'type') {
                        return parseFloat(data) || 0;
                    }
                    return data;
                }
            },
            {
                "targets": [3], 
                "type": "string",
                "render": function(data, type, row) {
                    if (type === 'sort' || type === 'type') {
                        return data.includes('badge-success') ? 1 : 0;
                    }
                    return data;
                }
            },
            {
                "targets": [0], 
                "orderable": true
            },
            {
                "targets": [1], 
                "orderable": true
            },
            {
                "targets": [2], 
                "orderable": true,
                "type": "date"
            },
            {
                "targets": [5],
                "orderable": false 
            }
        ],
        "order": [[0, "asc"]],
        "drawCallback": function(settings) {
            $('[data-toggle="tooltip"]').tooltip();
        }
    });

    $('[data-toggle="tooltip"]').tooltip();

    // Create Bucket
    $("#createBucketForm").submit(function(e) {
        e.preventDefault();
        const data = { 
            bucket_name: $("#bucketName").val(),
            region: $("#bucketRegion").val(),
            enable_locking: $("#bucketLocking").is(":checked")
        };
        const $result = $("#createBucketResult");
        $result.html('');
        
        $.ajax({
            url: "/create_bucket",
            type: "POST",
            contentType: "application/json",
            data: JSON.stringify(data),
            success: function(response) {
                if(response.success) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Bucket Created',
                        text: `Bucket "${data.bucket_name}" created successfully`,
                        timer: 2000,
                        showConfirmButton: false
                    }).then(() => location.reload());
                } else {
                    $result.html('<div class="alert alert-danger">' + (response.message || "Error creating bucket.") + '</div>');
                }
            },
            error: function(err) {
                $result.html('<div class="alert alert-danger">AJAX error: ' + err.statusText + '</div>');
            }
        });
    });

    // Delete Bucket
    $(document).on("click", ".delete-bucket-btn", function() {
        const bucketName = $(this).data("bucket");

        Swal.fire({
            title: 'Delete Bucket',
            html: `Are you sure you want to delete bucket <strong>"${bucketName}"</strong>?<br><br>
                   <small class="text-danger">⚠️ This action cannot be undone!</small>`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Yes, delete it!',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                Swal.fire({
                    title: 'Deleting Bucket...',
                    text: 'Please wait while we delete the bucket',
                    allowOutsideClick: false,
                    didOpen: function() {
                        Swal.showLoading();
                    }
                });

                $.ajax({
                    url: "/delete_bucket",
                    type: "POST",
                    contentType: "application/json",
                    data: JSON.stringify({ bucket_name: bucketName }),
                    success: function(response) {
                        Swal.close();
                        if(response.success) {
                            Swal.fire({
                                icon: 'success',
                                title: 'Bucket Deleted!',
                                text: `Bucket "${bucketName}" has been deleted successfully`,
                                timer: 2000,
                                showConfirmButton: false
                            }).then(() => location.reload());
                        } else {
                            Swal.fire({
                                icon: 'error',
                                title: 'Cannot Delete Bucket',
                                html: `❌ ${response.message || "Failed to delete bucket."}<br><br>
                                       <small>Please empty the bucket first and try again.</small>`
                            });
                        }
                    },
                    error: function(err) {
                        Swal.close();
                        let errorMessage = "An error occurred while deleting the bucket.";
                        
                        if (err.responseJSON && err.responseJSON.message) {
                            errorMessage = err.responseJSON.message;
                        } else if (err.statusText) {
                            errorMessage = `Server error: ${err.statusText}`;
                        }
                        
                        Swal.fire({
                            icon: 'error',
                            title: 'Delete Failed',
                            text: errorMessage
                        });
                    }
                });
            }
        });
    });

    $(document).on("click", ".versioning-btn", function() {
        const bucketName = $(this).data("bucket");
        const $btn = $(this);
        const originalText = $btn.html();
        
        $btn.prop("disabled", true).html('<i class="fas fa-spinner fa-spin"></i> Processing...');

        const $row = $btn.closest('tr');
        const $versioningBadge = $row.find('td').eq(3).find('.badge');
        const isCurrentlyEnabled = $versioningBadge.hasClass('badge-success');
        
        const action = isCurrentlyEnabled ? "disable" : "enable";

        fetch("/toggle_versioning", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bucket_name: bucketName, action: action })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                const newStatus = action === 'enable' ? 'Enabled' : 'Disabled';
                Swal.fire({
                    icon: 'success',
                    title: 'Versioning Updated',
                    text: `Versioning for bucket "${bucketName}" is now ${newStatus}`,
                    timer: 2000,
                    showConfirmButton: false
                }).then(() => location.reload());
            } else {
                throw new Error(data.message || "Failed to update versioning");
            }
        })
        .catch(err => {
            Swal.fire('Error', err.message || "Failed to update versioning", 'error');
            $btn.html(originalText).prop("disabled", false);
        });
    });

    // Manage Tags
    let currentBucket = null;

    function loadTags(bucketName) {
        fetch(`/get_bucket_tags?bucket_name=${bucketName}`)
            .then(res => res.json())
            .then(data => {
                const tbody = $("#tagsTable tbody");
                tbody.empty();
                if (data.success && data.tags) {
                    data.tags.forEach(tag => {
                        tbody.append(`
                            <tr>
                                <td>${tag.Key}</td>
                                <td>${tag.Value}</td>
                                <td>
                                    <button class="btn btn-sm btn-danger delete-tag-btn" data-key="${tag.Key}">
                                        <i class="fas fa-trash"></i> Delete
                                    </button>
                                </td>
                            </tr>
                        `);
                    });
                } else {
                    tbody.append('<tr><td colspan="3" class="text-center">No tags found</td></tr>');
                }
            });
    }

    $(document).on("click", ".manage-tags-btn", function() {
        currentBucket = $(this).data("bucket");
        $("#tagsBucketName").text(currentBucket);
        loadTags(currentBucket);
        $("#manageTagsModal").modal("show");
    });

    $(document).on("click", ".delete-tag-btn", function() {
        const key = $(this).data("key");
        fetch("/delete_bucket_tag", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bucket_name: currentBucket, key: key })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Tag Deleted',
                    text: `Tag "${key}" deleted successfully`,
                    timer: 1500,
                    showConfirmButton: false
                });
                loadTags(currentBucket);
            } else {
                Swal.fire('Error', data.message || "Failed to delete tag", 'error');
            }
        });
    });

    $("#addNewTagBtn").click(function() {
        const key = $("#newTagKey").val().trim();
        const value = $("#newTagValue").val().trim();
        if (!key || !value) {
            Swal.fire('Warning', 'Both key and value are required.', 'warning');
            return;
        }
        fetch("/add_bucket_tag", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ bucket_name: currentBucket, key: key, value: value })
        })
        .then(res => res.json())
        .then(data => {
            if (data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Tag Added',
                    text: `Tag "${key}" added successfully`,
                    timer: 1500,
                    showConfirmButton: false
                });
                $("#newTagKey").val("");
                $("#newTagValue").val("");
                loadTags(currentBucket);
            } else {
                Swal.fire('Error', data.message || "Failed to add tag", 'error');
            }
        });
    });

    // Bucket Policy Management
    let currentPolicyBucket = null;
    let currentPolicyRaw = null;

    $(document).on("click", ".policy-btn", function() {
        currentPolicyBucket = $(this).data("bucket");
        $("#policyBucketName").text(currentPolicyBucket);
        $("#policyContent").text("Loading policy...");
        $("#policyEditorSection").hide();
        $("#editPolicyBtn").show();
        $("#bucketPolicyModal").modal("show");

        fetch(`/get_bucket_policies?bucket_name=${currentPolicyBucket}`)
            .then(res => res.json())
            .then(data => {
                if(data.success && data.policies && data.policies.length > 0) {
                    currentPolicyRaw = data.policies[0];
                    $("#policyContent").text(JSON.stringify(JSON.parse(currentPolicyRaw), null, 2));
                } else {
                    currentPolicyRaw = null;
                    $("#policyContent").text("No policy found.");
                }
            })
            .catch(err => {
                $("#policyContent").text("Error loading policy: " + err);
            });
    });

    $("#editPolicyBtn").click(function() {
        $("#policyContent").hide();
        $("#editPolicyBtn").hide();

        if(currentPolicyRaw) {
            $("#policyEditor").val(JSON.stringify(JSON.parse(currentPolicyRaw), null, 2));
        } else {
            $("#policyEditor").val(`{
  "Version": "2012-10-17",
  "Statement": []
}`);
        }
        $("#policyEditorSection").show();
    });

    $("#cancelPolicyBtn").click(function() {
        $("#policyEditorSection").hide();
        $("#policyContent").show();
        $("#editPolicyBtn").show();
    });

    $("#savePolicyBtn").click(function() {
        let newPolicy = $("#policyEditor").val();
        try {
            JSON.parse(newPolicy);
        } catch(e) {
            Swal.fire('Error', "Invalid JSON format: " + e.message, 'error');
            return;
        }

        fetch("/set_bucket_policy", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                bucket_name: currentPolicyBucket,
                policy: newPolicy
            })
        })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Policy Saved',
                    text: 'Bucket policy updated successfully',
                    timer: 1500,
                    showConfirmButton: false
                });
                $("#policyContent").text(JSON.stringify(JSON.parse(newPolicy), null, 2)).show();
                $("#policyEditorSection").hide();
                $("#editPolicyBtn").show();
                currentPolicyRaw = newPolicy;
            } else {
                Swal.fire('Error', data.message || "Failed to save policy", 'error');
            }
        })
        .catch(err => Swal.fire('Error', "Server error: " + err, 'error'));
    });

    $("#deletePolicyBtn").click(function() {
        if(!currentPolicyBucket) {
            Swal.fire('Warning', "Bucket not selected!", 'warning');
            return;
        }

        Swal.fire({
            title: 'Delete Policy',
            text: `Are you sure you want to delete the policy for ${currentPolicyBucket}?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Yes, delete it!',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                fetch("/delete_bucket_policy", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ bucket_name: currentPolicyBucket })
                })
                .then(res => res.json())
                .then(data => {
                    if(data.success) {
                        Swal.fire({
                            icon: 'success',
                            title: 'Policy Deleted',
                            text: 'Bucket policy deleted successfully',
                            timer: 1500,
                            showConfirmButton: false
                        });
                        $("#bucketPolicyModal").modal("hide");
                    } else {
                        Swal.fire('Error', data.message || "Failed to delete policy", 'error');
                    }
                })
                .catch(err => Swal.fire('Error', "Server error: " + err, 'error'));
            }
        });
    });

    // Lifecycle Management
    let currentLifecycleBucket = null;
    let currentLifecycleRaw = null;

    $(document).on("click", ".lifecycle-btn", function() {
        currentLifecycleBucket = $(this).data("bucket");
        $("#lifecycleBucketName").text(currentLifecycleBucket);
        $("#lifecycleContent").text("Loading lifecycle configuration...");
        $("#lifecycleEditorSection").hide();
        $("#editLifecycleBtn").show();
        $("#bucketLifecycleModal").modal("show");

        fetch(`/get_bucket_lifecycle?bucket_name=${currentLifecycleBucket}`)
            .then(res => res.json())
            .then(data => {
                if(data.success && data.lifecycle && data.lifecycle.length > 0) {
                    currentLifecycleRaw = JSON.stringify(data.lifecycle, null, 2);
                    $("#lifecycleContent").text(currentLifecycleRaw);
                } else {
                    currentLifecycleRaw = null;
                    $("#lifecycleContent").text("No lifecycle configuration found.");
                }
            })
            .catch(err => {
                $("#lifecycleContent").text("Error loading lifecycle: " + err);
            });
    });

    $("#editLifecycleBtn").click(function() {
        $("#lifecycleContent").hide();
        $("#editLifecycleBtn").hide();

        if(currentLifecycleRaw) {
            $("#lifecycleEditor").val(currentLifecycleRaw);
        } else {
            $("#lifecycleEditor").val(`[
  {
    "ID": "ExpireOldObjects",
    "Status": "Enabled",
    "Filter": { "Prefix": "" },
    "Expiration": { "Days": 30 }
  }
]`);
        }
        $("#lifecycleEditorSection").show();
    });

    $("#cancelLifecycleBtn").click(function() {
        $("#lifecycleEditorSection").hide();
        $("#lifecycleContent").show();
        $("#editLifecycleBtn").show();
    });

    $("#saveLifecycleBtn").click(function() {
        let newLifecycle = $("#lifecycleEditor").val();
        try {
            JSON.parse(newLifecycle);
        } catch(e) {
            Swal.fire('Error', "Invalid JSON format: " + e.message, 'error');
            return;
        }

        fetch("/set_bucket_lifecycle", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify({
                bucket_name: currentLifecycleBucket,
                lifecycle: newLifecycle
            })
        })
        .then(res => res.json())
        .then(data => {
            if(data.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Lifecycle Saved',
                    text: 'Lifecycle configuration updated successfully',
                    timer: 1500,
                    showConfirmButton: false
                });
                $("#lifecycleContent").text(JSON.stringify(JSON.parse(newLifecycle), null, 2)).show();
                $("#lifecycleEditorSection").hide();
                $("#editLifecycleBtn").show();
                currentLifecycleRaw = newLifecycle;
            } else {
                Swal.fire('Error', data.message || "Failed to save lifecycle", 'error');
            }
        })
        .catch(err => Swal.fire('Error', "Server error: " + err, 'error'));
    });

    $("#deleteLifecycleBtn").click(function() {
        if(!currentLifecycleBucket) return Swal.fire('Warning', "Bucket not selected", 'warning');
        
        Swal.fire({
            title: 'Delete Lifecycle',
            text: `Are you sure you want to delete lifecycle configuration for ${currentLifecycleBucket}?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Yes, delete it!',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                fetch("/delete_bucket_lifecycle", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({ bucket_name: currentLifecycleBucket })
                })
                .then(res => res.json())
                .then(data => {
                    if(data.success) {
                        Swal.fire({
                            icon: 'success',
                            title: 'Lifecycle Deleted',
                            text: 'Lifecycle configuration deleted successfully',
                            timer: 1500,
                            showConfirmButton: false
                        });
                        $("#bucketLifecycleModal").modal("hide");
                    } else {
                        Swal.fire('Error', data.message || "Failed to delete lifecycle", 'error');
                    }
                })
                .catch(err => Swal.fire('Error', "Server error: " + err, 'error'));
            }
        });
    });

    // Replication Management
    let currentReplicationBucket = null;
    let currentReplicationRaw = null;

    function openReplicationModal(bucketName) {
        currentReplicationBucket = bucketName;
        $("#replicationBucketName").text(bucketName);
        $("#replicationContent").text("Loading replication rules...");
        $("#replicationEditorSection").hide();
        $("#editReplicationBtn").show();
        $("#replicationModal").modal("show");

        fetch(`/get_bucket_replication?bucket_name=${bucketName}`)
            .then(res => res.json())
            .then(data => {
                if (data && data.replication && data.replication.Rules) {
                    currentReplicationRaw = JSON.stringify(data.replication.Rules, null, 2);
                    $("#replicationContent").text(currentReplicationRaw);
                } else {
                    currentReplicationRaw = null;
                    $("#replicationContent").text("No replication rules found.");
                }
            })
            .catch(err => {
                $("#replicationContent").text("Error loading replication rules: " + err);
            });
    }

    $(document).on("click", ".replication-btn", function(e) {
        e.stopPropagation();
        const bucketName = $(this).data("bucket");
        openReplicationModal(bucketName);
    });

    $("#editReplicationBtn").click(function(e) {
        e.stopPropagation();
        e.preventDefault();
        
        $("#replicationContent").hide();
        $("#editReplicationBtn").hide();

        if(currentReplicationRaw) {
            $("#replicationEditor").val(currentReplicationRaw);
        } else {
            $("#replicationEditor").val("[]");
        }
        $("#replicationEditorSection").show();
        
        return false;
    });

    $("#cancelReplicationBtn").click(function(e) {
        e.stopPropagation();
        e.preventDefault();
        
        $("#replicationEditorSection").hide();
        $("#replicationContent").show();
        $("#editReplicationBtn").show();
        
        return false;
    });

    $("#saveReplicationBtn").click(function(e) {
        e.stopPropagation();
        e.preventDefault();
        
        let newReplication = $("#replicationEditor").val();
        let rules = [];
        try {
            rules = JSON.parse(newReplication);
        } catch (e) {
            Swal.fire('Error', "Invalid JSON format", 'error');
            return false;
        }

        fetch("/apply_replication_rule", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                bucket_name: currentReplicationBucket,
                replication: {
                    Role: "", 
                    Rules: rules
                }
            })
        })
        .then(res => res.json())
        .then(result => {
            if(result.success) {
                Swal.fire({
                    icon: 'success',
                    title: 'Replication Saved',
                    text: 'Replication rules updated successfully',
                    timer: 1500,
                    showConfirmButton: false
                });
                $("#replicationContent").text(JSON.stringify(rules, null, 2)).show();
                $("#replicationEditorSection").hide();
                $("#editReplicationBtn").show();
                currentReplicationRaw = newReplication;
            } else {
                Swal.fire('Error', result.message || "Failed to save replication rules", 'error');
            }
        })
        .catch(err => {
            Swal.fire('Error', "Error saving replication rules: " + err, 'error');
        });
        
        return false;
    });

    $("#deleteReplicationBtn").click(function(e) {
        e.stopPropagation();
        e.preventDefault();
        
        if(!currentReplicationBucket) return Swal.fire('Warning', "Bucket not selected", 'warning');
        
        Swal.fire({
            title: 'Delete Replication',
            text: `Are you sure you want to delete replication rules for ${currentReplicationBucket}?`,
            icon: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#d33',
            cancelButtonColor: '#3085d6',
            confirmButtonText: 'Yes, delete it!',
            cancelButtonText: 'Cancel'
        }).then((result) => {
            if (result.isConfirmed) {
                Swal.fire({
                    title: 'Deleting Replication...',
                    text: 'Please wait',
                    allowOutsideClick: false,
                    didOpen: function() {
                        Swal.showLoading();
                    }
                });

                fetch("/delete_bucket_replication", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ bucket_name: currentReplicationBucket })
                })
                .then(res => res.json())
                .then(data => {
                    Swal.close();
                    if(data.success) {
                        Swal.fire({
                            icon: 'success',
                            title: 'Replication Deleted',
                            text: data.message || 'Replication rules deleted successfully',
                            timer: 1500,
                            showConfirmButton: false
                        });
                        $("#replicationContent").text("No replication rules found.");
                        currentReplicationRaw = null;
                        setTimeout(function() {
                            $("#replicationModal").modal("hide");
                        }, 1500);
                    } else {
                        Swal.fire('Error', data.message || "Failed to delete replication rules", 'error');
                    }
                })
                .catch(err => {
                    Swal.close();
                    Swal.fire('Error', "Error deleting replication rules: " + err, 'error');
                });
            }
        });
        
        return false;
    });
});