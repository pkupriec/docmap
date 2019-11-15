FROM mcr.microsoft.com/dotnet/core/runtime:3.0-buster-slim AS base
WORKDIR /app

FROM mcr.microsoft.com/dotnet/core/sdk:3.0-buster AS build
WORKDIR /src
COPY ["doc_loader_http_elastic/doc_loader_http_elastic.csproj", "doc_loader_http_elastic/"]
RUN dotnet restore "doc_loader_http_elastic/doc_loader_http_elastic.csproj"
COPY . .
WORKDIR "/src/doc_loader_http_elastic"
RUN dotnet build "doc_loader_http_elastic.csproj" -c Release -o /app/build

FROM build AS publish
RUN dotnet publish "doc_loader_http_elastic.csproj" -c Release -o /app/publish

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .
ENTRYPOINT ["dotnet", "doc_loader_http_elastic.dll"]