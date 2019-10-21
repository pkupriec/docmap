using System;
using System.Collections.Generic;
using System.Text;

namespace doc_loader_http_elastic
{
    class PlainDocument
    {
        private string pageSource ;
        private DateTime uploadedAt;
        private string title;
        private int Id;
        public string PageSource { get => pageSource; set => pageSource = value; }
        public DateTime UploadedAt { get => uploadedAt; set => uploadedAt = value; }
        public string Title { get => title; set => title = value; }
        public int id { get => Id; set => Id = value; }
    }
}
