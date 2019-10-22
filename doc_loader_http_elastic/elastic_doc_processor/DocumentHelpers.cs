using System;
using System.Collections.Generic;
using System.Text;
using HtmlAgilityPack;

namespace elastic_doc_processor
{
    static class DocumentHelpers
    {
        static public string RemoveHtmlTags(string value)
        {
            HtmlDocument htmlDoc = new HtmlDocument();
            htmlDoc.LoadHtml(value);

            if (htmlDoc == null)
                return value;

            return htmlDoc.DocumentNode.InnerText;
        }

        static public string  GetTextBetweenSubstrings (string document, string begin,string end)
        {
            string FinalString = "";
            int Pos1 = document.IndexOf(begin) + begin.Length;
            int Pos2 = document.IndexOf(end, Pos1);
            FinalString = document.Substring(Pos1, Pos2 - Pos1);
            return FinalString;
        }

        static public string GetScpDocumentContainmentClass(string document)
        {
            var searchPatterns = new List<ScpDocumentContainmentClassPattern>
            {
                new ScpDocumentContainmentClassPattern(){beginPattern = "<p><strong>Object Class",endPattern =  "</p>"},
                new ScpDocumentContainmentClassPattern(){beginPattern = "<p><strong>Object Class:",endPattern =  "</p>"},
                new ScpDocumentContainmentClassPattern(){beginPattern = "<h1><span>Object Class:",endPattern =  "</span></h1>"},
                new ScpDocumentContainmentClassPattern(){beginPattern = "<p><span class=\"h - span\"><strong>Object Class",endPattern =  "</p>"},
                new ScpDocumentContainmentClassPattern(){beginPattern = "<strong>Object Class:",endPattern =  "<br />"},
                new ScpDocumentContainmentClassPattern(){beginPattern = "2bold%22%3EObject%20Class%3A%3C%2Ftspan%3E%20",endPattern =  "%3C%2F"},
                new ScpDocumentContainmentClassPattern(){beginPattern = "<div class=\"obj-text\">",endPattern =  "</div>"},
                new ScpDocumentContainmentClassPattern(){beginPattern = "<strong>Object Class:</strong> <span style=\"text-decoration: line - through; \">",endPattern =  "</div>"}
            };
            string ObjectClass = "";
            foreach (ScpDocumentContainmentClassPattern pattern in searchPatterns)
            {
                ObjectClass = DocumentHelpers.GetTextBetweenSubstrings(document, pattern.beginPattern,pattern.endPattern);
                if (ObjectClass != "") break;
            }
            if (ObjectClass == null) ObjectClass = "NOT PARSED";
            
            return ObjectClass.Replace("</strong>", "").Replace(":", "").Trim();
        }

    }

    public class ScpDocumentContainmentClassPattern
    {
        public string beginPattern;
        public string endPattern;
    }
}
