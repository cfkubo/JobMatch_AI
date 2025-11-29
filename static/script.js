document.addEventListener('DOMContentLoaded', () => {
    const resumeFile = document.getElementById('resumeFile');
    const uploadButton = document.getElementById('uploadButton');
    const uploadStatus = document.getElementById('uploadStatus');
    const aiAnalysisResults = document.getElementById('aiAnalysisResults');
    const searchJobsButton = document.getElementById('searchJobsButton');
    const webSearchResults = document.getElementById('webSearchResults');

    let uploadedResumeText = "";
    let currentAnalysis = null; // Store the parsed AI analysis

    uploadButton.addEventListener('click', async () => {
        const file = resumeFile.files[0];
        if (!file) {
            uploadStatus.textContent = "Please select a resume file.";
            uploadStatus.style.color = "red";
            return;
        }

        uploadStatus.textContent = "Uploading and analyzing...";
        uploadStatus.style.color = "orange";
        aiAnalysisResults.innerHTML = '<p>Analyzing...</p>';
        searchJobsButton.style.display = 'none';
        webSearchResults.innerHTML = '<p>Web search results will appear here.</p>';

        const formData = new FormData();
        formData.append('resume', file);

        try {
            // Upload resume
            const uploadResponse = await fetch('/api/upload_resume', {
                method: 'POST',
                body: formData
            });
            const uploadResult = await uploadResponse.json();

            if (!uploadResponse.ok) {
                throw new Error(uploadResult.error || 'Failed to upload resume');
            }

            uploadStatus.textContent = "Resume uploaded successfully!";
            uploadStatus.style.color = "green";
            uploadedResumeText = uploadResult.resume_text;

            // Analyze resume
            const analyzeResponse = await fetch('/api/analyze_resume', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ resume_text: uploadedResumeText })
            });
            const analyzeResult = await analyzeResponse.json();

            if (!analyzeResponse.ok) {
                throw new Error(analyzeResult.error || 'Failed to analyze resume');
            }

            currentAnalysis = analyzeResult.analysis; // Store the full analysis object

            let analysisHtml = '<h3>Resume Analysis:</h3>';
            analysisHtml += `<p><strong>Summary:</strong> ${currentAnalysis.summary || 'N/A'}</p>`;
            analysisHtml += `<p><strong>Skills:</strong> ${currentAnalysis.skills ? currentAnalysis.skills.join(', ') : 'N/A'}</p>`;
            analysisHtml += `<p><strong>Industries:</strong> ${currentAnalysis.industries ? currentAnalysis.industries.join(', ') : 'N/A'}</p>`;
            analysisHtml += `<p><strong>Suggested Companies:</strong> ${currentAnalysis.suggested_companies ? currentAnalysis.suggested_companies.join(', ') : 'N/A'}</p>`;
            analysisHtml += `<p><strong>Suggested Roles/Keywords:</strong> ${currentAnalysis.suggested_roles ? currentAnalysis.suggested_roles.join(', ') : 'N/A'}</p>`;
            aiAnalysisResults.innerHTML = analysisHtml;
            
            searchJobsButton.style.display = 'block'; // Show search button after analysis

        } catch (error) {
            uploadStatus.textContent = `Error: ${error.message}`;
            uploadStatus.style.color = "red";
            aiAnalysisResults.innerHTML = '<p>Analysis failed.</p>';
        }
    });

    searchJobsButton.addEventListener('click', async () => {
        if (!currentAnalysis) {
            webSearchResults.innerHTML = '<p>Please upload and analyze a resume first.</p>';
            return;
        }

        webSearchResults.innerHTML = '<p>Searching for jobs based on AI analysis...</p>';
        
        try {
            const searchResponse = await fetch('/api/web_search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ analysis: currentAnalysis }) // Send the full analysis
            });
            const searchResult = await searchResponse.json();

            if (!searchResponse.ok) {
                throw new Error(searchResult.error || 'Failed to perform web search');
            }

            let resultsHtml = '<h3>Web Search Results:</h3>';
            if (searchResult.results && searchResult.results.length > 0) {
                // Group results by query_type for better presentation
                const groupedResults = searchResult.results.reduce((acc, item) => {
                    const type = item.query_type || 'unspecified';
                    if (!acc[type]) {
                        acc[type] = [];
                    }
                    acc[type].push(item);
                    return acc;
                }, {});

                for (const type in groupedResults) {
                    const title = type.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase());
                    resultsHtml += `<h4>${title}</h4>`;
                    groupedResults[type].forEach(item => {
                        resultsHtml += `
                            <div class="search-item">
                                <h5><a href="${item.url}" target="_blank">${item.title}</a></h5>
                                <p>${item.description}</p>
                                <p><small>${item.url}</small></p>
                            </div>
                        `;
                    });
                }
            } else {
                resultsHtml += '<p>No relevant results found.</p>';
            }
            webSearchResults.innerHTML = resultsHtml;

        } catch (error) {
            webSearchResults.innerHTML = `<p style="color:red;">Error during web search: ${error.message}</p>`;
        }
    });
});
