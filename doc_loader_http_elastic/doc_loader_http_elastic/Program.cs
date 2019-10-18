using System;
using System.Net;
using System.Collections.Generic;
using Nest;
//using Elasticsearch.Net;

namespace doc_loader_http_elastic
{
    class Program
    {
        

        static void Main(string[] args)
        {
            var documents = new Docloader();
            var ConnectedElastic = new ElasticInteractionWrapper();
            ConnectedElastic.OpenElasticConnection();

            

            List<string> MasterPages = new List<string>()
            {
                { "http://www.scp-wiki.net/scp-series" },
                { "http://www.scp-wiki.net/scp-series-2" },
                { "http://www.scp-wiki.net/scp-series-3" },
                { "http://www.scp-wiki.net/scp-series-4" },
                { "http://www.scp-wiki.net/scp-series-5" }
            };
            foreach (string url in documents.GetSubDocumentUrls(MasterPages, "//a[@href]"))
            {
                Console.WriteLine(url);
                PlainDocument pd = new PlainDocument();
                pd.Page = documents.GetDocumentByUrl(url);
                pd.UploadedAt = DateTime.Now;
                var indexResponse = ConnectedElastic.SaveDocument(pd);
                if (indexResponse.IsValid)
                {
                    Console.WriteLine("sent to elastic");
                }

            }

            Console.ReadLine();
        }
    }
}
