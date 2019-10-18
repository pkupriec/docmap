using System;
using System.Collections.Generic;
using System.Text;
using System.Net;
using HtmlAgilityPack;
using System.Text.RegularExpressions;

namespace doc_loader_http_elastic
{
    class scpfoundation
    {
        private List<string> MasterPages = new List<string>()
        {
            { "http://www.scp-wiki.net/scp-series" },
            { "http://www.scp-wiki.net/scp-series-2" },
            { "http://www.scp-wiki.net/scp-series-3" },
            { "http://www.scp-wiki.net/scp-series-4" },
            { "http://www.scp-wiki.net/scp-series-5" }
        };
        private string pageRegexp = ".*scp-\\d.*";
        public List<string> getDocumentUrls ()
        {
            HtmlWeb hw = new HtmlWeb();
            List<string> DocumentURLs = new List<string> { };
            foreach (string masterPage in MasterPages)
                {
                HtmlDocument doc = hw.Load(masterPage);
                foreach (HtmlNode link in doc.DocumentNode.SelectNodes("//a[@href]"))
                {
                    string DocumentURl = link.GetAttributeValue("href", null);
                    if (Regex.IsMatch(DocumentURl, pageRegexp))
                        DocumentURLs.Add("http://www.scp-wiki.net"+link.GetAttributeValue("href", null));
                };
            }
            return DocumentURLs;
        }
    }
}
