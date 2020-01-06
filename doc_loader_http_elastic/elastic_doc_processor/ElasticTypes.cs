using System;
using System.Collections.Generic;
using System.Text;
using Google.Cloud.Language.V1;

namespace elastic_doc_processor
{
    class ScpSpecialContainmentDocument
    {
        private string Id;
        private string pageTitle;
        private string itemNumber;
        private string objectClass;
        private string specialContainmentProcedures;
        private string description;
        private string body;
        private string pageSource ;
        private DateTime uploadedAt;

        public string id { get => Id; set => Id = value; }
        public string PageTitle { get => pageTitle; set => pageTitle = value; }
        public string ItemNumber { get => itemNumber; set => itemNumber = value; }
        public string ObjectClass { get => objectClass; set => objectClass = value; }
        public string SpecialContainmentProcedures { get => specialContainmentProcedures; set => specialContainmentProcedures = value; }
        public string Description { get => description; set => description = value; }
        public string Body { get => body; set => body = value; }
        public string PageSource { get => pageSource; set => pageSource = value; }
        public languageAnalyzerResult languageAnalyzerResult { get => languageAnalyzerResult; set => languageAnalyzerResult = value; }
        public DateTime UploadedAt { get => uploadedAt; set => uploadedAt = value; }


    }
    class PlainDocument
    {
        private string pageSource;
        private DateTime uploadedAt;
        private string title;
        private int Id;
        public string PageSource { get => pageSource; set => pageSource = value; }
        public DateTime UploadedAt { get => uploadedAt; set => uploadedAt = value; }
        public string Title { get => title; set => title = value; }
        public int id { get => Id; set => Id = value; }
    }

    class languageAnalyzerResult
    {
        public Sentiment DocumentSentiment { get => DocumentSentiment; set => DocumentSentiment = value; }
    }
}

