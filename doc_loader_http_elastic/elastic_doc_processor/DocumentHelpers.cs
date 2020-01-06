using System;
using System.Collections.Generic;
using System.Text;
using HtmlAgilityPack;
using System.Text.RegularExpressions;

namespace elastic_doc_processor
{
    static class DocumentHelpers
    {
        static public string  GetTextBetweenSubstrings (string document, string begin,string end)
        {
            string FinalString = "";
            int Pos1 = document.IndexOf(begin);
            if (Pos1 < 0) return "";
            Pos1 += begin.Length;
            int Pos2 = document.IndexOf(end, Pos1);
            if (Pos2 < 0) return "";
            FinalString = document.Substring(Pos1, Pos2 - Pos1);
            return FinalString;
        }

        static public string GetDocumentPart(string document, List<DocumentParsingPattern> searchPatterns)
        {
           
            string DocumentPart = "";
            foreach (DocumentParsingPattern pattern in searchPatterns)
            {
                DocumentPart = DocumentHelpers.GetTextBetweenSubstrings(document, pattern.beginPattern,pattern.endPattern)
                    .Trim();
                if (DocumentPart != "") break;
            }
            
            if (DocumentPart == "") DocumentPart = "NOT PARSED";
            DocumentPart = Regex.Replace(DocumentPart, "<.*?>", " ");
            return DocumentPart
                .Replace("</strong>", "")
                .Replace(":", "")
                .ToLower()
                .Trim();
        }


        static public List<DocumentParsingPattern> ScpObjectClassSearchPatterns = new List<DocumentParsingPattern>
            {
                //scp-1561
                new DocumentParsingPattern(){beginPattern = "<p><strong>Royal Object Class:</strong>",endPattern =  "</p>"},
                //SCP-4487
                new DocumentParsingPattern(){beginPattern = "<p><strong>Anomaly Class",endPattern =  "</p>"},
                new DocumentParsingPattern(){beginPattern = "<p><strong>Object Class:</strong>",endPattern =  ">1</a></sup></p><p><strong>"},
                new DocumentParsingPattern(){beginPattern = "<strong>Object Class:</strong> <span style=\"text-decoration: line - through; \">",endPattern =  "</div>"},
                //scp-1458
                new DocumentParsingPattern(){beginPattern = "<p><strong>Object class</strong>:",endPattern =  "</p>"},
                new DocumentParsingPattern(){beginPattern = "<p><strong>Object Class",endPattern =  "</p>"},
                new DocumentParsingPattern(){beginPattern = "<p><strong>Object Class:",endPattern =  "</p>"},
                new DocumentParsingPattern(){beginPattern = "<h1><span>Object Class:",endPattern =  "</span></h1>"},
                new DocumentParsingPattern(){beginPattern = "<p><span class=\"h - span\"><strong>Object Class",endPattern =  "</p>"},
                new DocumentParsingPattern(){beginPattern = "<strong>Object Class:",endPattern =  "<br />"},
                new DocumentParsingPattern(){beginPattern = "2bold%22%3EObject%20Class%3A%3C%2Ftspan%3E%20",endPattern =  "%3C%2F"},
                new DocumentParsingPattern(){beginPattern = "<div class=\"obj-text\">",endPattern =  "</div>"},
                //scp-783
                new DocumentParsingPattern(){beginPattern = "<td><span style=\"font-size:125%;\"><strong>Object Class:",endPattern =  "</span></td>"},
                //scp-351 
                new DocumentParsingPattern(){beginPattern = "<div class=\"class-text\">",endPattern =  "</div>"}

            };
        static public List<DocumentParsingPattern> ScpObjectBodyPatterns = new List<DocumentParsingPattern>
            {
               //Generic
               new DocumentParsingPattern(){beginPattern = "<p><strong>Special Containment Procedures:</strong>",endPattern =  "<div class=\"footer-wikiwalk-nav\">"},
               //scp-1458
               new DocumentParsingPattern(){beginPattern = "<p><strong>Special Containment Procedures</strong>:",endPattern =  "<div class=\"footer-wikiwalk-nav\">"},
               //SCP-1654
               new DocumentParsingPattern(){beginPattern = "<p><strong>Protocol Instructions:</strong>",endPattern =  "<div class=\"footer-wikiwalk-nav\">"}
            };
    }

    public class DocumentParsingPattern
    {
        public string beginPattern;
        public string endPattern;
    }
}
