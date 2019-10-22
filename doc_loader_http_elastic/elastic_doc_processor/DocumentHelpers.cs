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
            string FinalString;
            int Pos1 = document.IndexOf(begin) + begin.Length;
            int Pos2 = document.IndexOf(end, Pos1);
            FinalString = document.Substring(Pos1, Pos2 - Pos1);
            return FinalString;
        }

        static public string GetScpDocumentContainmentClass(string document)
        {

            return document;
        }

    }
}
