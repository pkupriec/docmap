using System;
using System.Net;


namespace doc_loader_http_elastic
{
    class Program
    {
        static void Main(string[] args)
        {
            Console.WriteLine("Hello World!");
            scpfoundation documents = new scpfoundation();
            foreach (string url in documents.getDocumentUrls())
            {
                Console.WriteLine(url);
            }

            Console.ReadLine();
        }
    }
}
