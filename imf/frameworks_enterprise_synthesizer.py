"""
Modern Frameworks & Enterprise Runtimes Synthesizer (IMF).
Covers the most dominant production frameworks and enterprise runtimes in 2026:
1. .NET 8 / 9 / C# 12 (ASP.NET Core Minimal APIs, Entity Framework Core, LINQ, Dependency Injection).
2. Modern Web & Full-Stack (Next.js 15 App Router, React Server Components, TypeScript).
3. Enterprise Java (Spring Boot 3, Spring Data JPA, Jakarta EE).
4. Golang Enterprise Microservices (Gin / Chi, gRPC, context propagation, channels).
"""

from typing import List, Tuple
import random

class FrameworksEnterpriseSynthesizer:
    def __init__(self, seed: int = 101):
        self.rng = random.Random(seed)

    def generate_dotnet_csharp(self) -> str:
        samples = [
            ("// ASP.NET Core 8/9 Minimal API with Entity Framework Core & Dependency Injection\n"
             "using Microsoft.AspNetCore.Builder;\n"
             "using Microsoft.EntityFrameworkCore;\n"
             "using Microsoft.Extensions.DependencyInjection;\n\n"
             "var builder = WebApplication.CreateBuilder(args);\n"
             "builder.Services.AddDbContext<OrderDbContext>(opt => opt.UseNpgsql(builder.Configuration.GetConnectionString(\"Default\")));\n"
             "builder.Services.AddScoped<IOrderService, OrderService>();\n\n"
             "var app = builder.Build();\n"
             "app.MapGet(\"/api/orders/{id:guid}\", async (Guid id, IOrderService svc, CancellationToken ct) =>\n"
             "    await svc.GetOrderAsync(id, ct) is { } order ? Results.Ok(order) : Results.NotFound());\n\n"
             "app.MapPost(\"/api/orders\", async (CreateOrderDto dto, IOrderService svc, CancellationToken ct) => {\n"
             "    var created = await svc.CreateOrderAsync(dto, ct);\n"
             "    return Results.Created($\"/api/orders/{created.Id}\", created);\n"
             "});\n\n"
             "app.Run();"),
            
            ("// C# 12 / .NET Domain Model with Record Types & LINQ Aggregations\n"
             "public readonly record struct Money(decimal Amount, string Currency);\n\n"
             "public record OrderItem(Guid ProductId, int Quantity, Money UnitPrice);\n\n"
             "public sealed class OrderAggregate {\n"
             "    public Guid Id { get; init; } = Guid.NewGuid();\n"
             "    public List<OrderItem> Items { get; init; } = [];\n\n"
             "    public Money ComputeTotal() {\n"
             "        var total = Items.Sum(i => i.Quantity * i.UnitPrice.Amount);\n"
             "        return new Money(total, \"USD\");\n"
             "    }\n"
             "}")
        ]
        return self.rng.choice(samples)

    def generate_modern_web_react(self) -> str:
        samples = [
            ("// Next.js 15 App Router: React Server Component with Streaming Suspense\n"
             "import { Suspense } from 'react';\n"
             "import { db } from '@/lib/database';\n\n"
             "async function OrderAnalyticsFeed() {\n"
             "  const metrics = await db.orders.aggregate({\n"
             "    _sum: { totalAmount: true },\n"
             "    _count: { id: true }\n"
             "  });\n"
             "  return (\n"
             "    <div className=\"grid grid-cols-2 gap-4\">\n"
             "      <div className=\"p-4 rounded border\">Volume: {metrics._count.id}</div>\n"
             "      <div className=\"p-4 rounded border\">Revenue: ${metrics._sum.totalAmount?.toLocaleString()}</div>\n"
             "    </div>\n"
             "  );\n"
             "}\n\n"
             "export default function DashboardPage() {\n"
             "  return (\n"
             "    <main className=\"container mx-auto p-6\">\n"
             "      <h1 className=\"text-2xl font-bold\">Operations</h1>\n"
             "      <Suspense fallback={<p>Streaming telemetry...</p>}>\n"
             "        <OrderAnalyticsFeed />\n"
             "      </Suspense>\n"
             "    </main>\n"
             "  );\n"
             "}"),
            
            ("// TypeScript Zod Schema Validation & Server Action Mutation\n"
             "'use server';\n"
             "import { z } from 'zod';\n"
             "import { revalidatePath } from 'next/cache';\n\n"
             "const CreateTeamSchema = z.object({\n"
             "  name: z.string().min(3).max(64),\n"
             "  tier: z.enum(['starter', 'enterprise'])\n"
             "});\n\n"
             "export async function createTeamAction(formData: FormData) {\n"
             "  const parsed = CreateTeamSchema.safeParse({\n"
             "    name: formData.get('name'),\n"
             "    tier: formData.get('tier')\n"
             "  });\n"
             "  if (!parsed.success) return { error: parsed.error.flatten() };\n"
             "  await db.teams.create({ data: parsed.data });\n"
             "  revalidatePath('/dashboard/teams');\n"
             "  return { success: true };\n"
             "}")
        ]
        return self.rng.choice(samples)

    def generate_spring_boot_java(self) -> str:
        samples = [
            ("// Spring Boot 3 Enterprise REST Controller with Spring Data JPA\n"
             "package com.corp.ledger.api;\n\n"
             "import org.springframework.web.bind.annotation.*;\n"
             "import org.springframework.http.ResponseEntity;\n"
             "import java.util.UUID;\n\n"
             "@RestController\n"
             "@RequestMapping(\"/api/v1/accounts\")\n"
             "public class AccountController {\n"
             "    private final AccountRepository accountRepo;\n\n"
             "    public AccountController(AccountRepository accountRepo) {\n"
             "        this.accountRepo = accountRepo;\n"
             "    }\n\n"
             "    @GetMapping(\"/{id}\")\n"
             "    public ResponseEntity<AccountDto> getAccount(@PathVariable UUID id) {\n"
             "        return accountRepo.findById(id)\n"
             "            .map(AccountDto::fromEntity)\n"
             "            .map(ResponseEntity::ok)\n"
             "            .orElseGet(() -> ResponseEntity.notFound().build());\n"
             "    }\n"
             "}")
        ]
        return self.rng.choice(samples)

    def generate_corpus(self, num_samples: int = 100) -> List[Tuple[str, str]]:
        corpus = []
        generators = [
            (self.generate_dotnet_csharp, "framework_dotnet_csharp_aspnet"),
            (self.generate_modern_web_react, "framework_nextjs_react_fullstack"),
            (self.generate_spring_boot_java, "framework_java_spring_boot")
        ]
        for _ in range(num_samples):
            fn, tag = self.rng.choice(generators)
            corpus.append((fn(), tag))
        return corpus


if __name__ == "__main__":
    syn = FrameworksEnterpriseSynthesizer()
    c = syn.generate_corpus(3)
    for txt, tag in c:
        print(f"=== {tag} ===")
        print(txt[:250] + "...\n")
