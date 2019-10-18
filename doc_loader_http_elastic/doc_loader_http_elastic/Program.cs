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
            Docloader documents = new Docloader();
            var ElasticUri = new Uri("http://104.197.115.64:9200");
            var ElasticConnectionSettings = new ConnectionSettings(ElasticUri)
                .BasicAuthentication ("elastic","elpass")
                .DisableAutomaticProxyDetection()
                .DisableDirectStreaming()
                .PrettyJson()
                .DefaultIndex ("scp_documents_v01")
                .RequestTimeout(TimeSpan.FromMinutes(2));

            var client = new ElasticClient(ElasticConnectionSettings);

            

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
                pd.Body = documents.GetDocumentByUrl(url);
                var indexResponse = client.IndexDocument(pd);
                if (indexResponse.IsValid)
                {
                    Console.WriteLine("sent to elastic");
                }

            }

            Console.ReadLine();
        }
    }
}
