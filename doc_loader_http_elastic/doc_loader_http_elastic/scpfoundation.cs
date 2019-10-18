using System;
using System.Collections.Generic;
using System.Text;
using System.Net;
using HtmlAgilityPack;
using System.Text.RegularExpressions;

namespace doc_loader_http_elastic
{
    class Docloader
    {
       
        private string pageRegexp = ".*scp-\\d.*";
        public List<string> GetSubDocumentUrls(List<string> masterUrls,string urlPattern)
        {
            HtmlWeb hw = new HtmlWeb();
            List<string> DocumentURLs = new List<string> { };
            foreach (string masterUrl in masterUrls)
                {
                HtmlDocument doc = hw.Load(masterUrl);
                foreach (HtmlNode link in doc.DocumentNode.SelectNodes(urlPattern))
                {
                    string DocumentURl = link.GetAttributeValue("href", null);
                    if (Regex.IsMatch(DocumentURl, pageRegexp))
                        DocumentURLs.Add("http://www.scp-wiki.net"+link.GetAttributeValue("href", null));
                };
            }
            return DocumentURLs;
        }
        public string GetDocumentByUrl(string url)
        {
            HtmlWeb hw = new HtmlWeb();
            return hw.Load(url).DocumentNode.OuterHtml;
        }
    }
}
