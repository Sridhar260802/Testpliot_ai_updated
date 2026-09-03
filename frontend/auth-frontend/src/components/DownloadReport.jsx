import React, { useState } from 'react';
import axios from 'axios';

export default function DownloadReport() {
  const [isLoading, setIsLoading] = useState(false);

  const downloadReportFromBackend = async () => {
    setIsLoading(true);
    try {
      // Inga unga backend API URL-a unga thevaikku yetpa mathikkonga
      const response = await axios.get('http://localhost:5000/api/report/download', {
        responseType: 'blob', // PDF file receive panna idhu romba mukkiyam
      });

      // Blob-a URL aaga mathi download panna veikirom
      const pdfBlob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(pdfBlob);
      
      // Temporary link create panni click panna veikirom
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', 'TestPilot_Website_Report.pdf'); 
      document.body.appendChild(link);
      link.click();
      
      // Clean up
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
      
    } catch (error) {
      console.error("Error downloading the PDF report:", error);
      alert("Report download aagalai. Server-a check pannunga.");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-4 flex justify-center">
      <button 
        onClick={downloadReportFromBackend}
        disabled={isLoading}
        className={`px-6 py-2 font-semibold text-white rounded shadow-md transition ${
          isLoading 
            ? 'bg-gray-400 cursor-not-allowed' 
            : 'bg-[#759223] hover:bg-[#5a701b]'
        }`}
      >
        {isLoading ? 'Downloading...' : 'Download PDF Report'}
      </button>
    </div>
  );
}