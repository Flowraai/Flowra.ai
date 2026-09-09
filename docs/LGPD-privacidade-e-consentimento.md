# Privacidade e Consentimento — Flowra Care (RASCUNHO / MODELO)

> ⚠️ **AVISO IMPORTANTE — LEIA ANTES DE USAR**
> Este é um **rascunho/modelo** para acelerar a conversa com um profissional. Ele
> **NÃO é aconselhamento jurídico** e **não deve ser publicado como está**. Dado de
> saúde é **dado pessoal sensível** (LGPD, art. 5º, II e art. 11) e envolve regras do
> **CFM** e do sigilo médico. **Faça revisar por um(a) advogado(a) de proteção de
> dados/saúde e valide os pontos clínicos com um(a) médico(a)** antes de usar com
> pacientes reais. Preencha os campos entre `[colchetes]`.

---

## Identificação

- **Controlador dos dados:** [RAZÃO SOCIAL], CNPJ [00.000.000/0001-00], [endereço].
- **Encarregado(a) pelo Tratamento de Dados (DPO):** [nome], [e-mail: dpo@...], [telefone].
- **Produto:** Flowra Care — acompanhamento de pacientes entre consultas (psiquiatria).
- **Vigência / versão:** v[1.0] — [data].

> Observação sobre papéis: o **médico/clínica** costuma ser **controlador** dos dados
> clínicos do paciente; a plataforma (Flowra) pode atuar como **operador**. Defina
> com o(a) advogado(a) quem é controlador e quem é operador, e reflita isso aqui e
> nos contratos (DPA) — o texto abaixo assume o médico/clínica como controlador.

---

## 1. Política de Privacidade

### 1.1 Quais dados tratamos
- **Identificação e contato:** nome, telefone/e-mail (cifrados em repouso).
- **Dados de saúde (sensíveis):** respostas do check-in diário (humor, ansiedade,
  sono, medicação, crises, efeitos colaterais, item de risco/autoagressão), texto/
  áudio livre, mensagens trocadas com o médico, adesão à medicação, consultas e exames.
- **Dados técnicos mínimos:** registros de acesso/segurança (sem conteúdo clínico).

### 1.2 Para que usamos (finalidade)
Permitir o **acompanhamento clínico entre consultas**, sinalizar ao médico situações
que exigem atenção (índice de risco) e organizar lembretes de medicação/consulta.
**A IA do produto apoia a priorização — não fornece diagnóstico** e não substitui o
julgamento do profissional.

### 1.3 Base legal (LGPD)
Para dado sensível de saúde, as bases aplicáveis podem incluir **consentimento
específico e destacado** (art. 11, I) e/ou **tutela da saúde por profissional/serviço
de saúde** (art. 11, II, "f"). **Definir com o(a) advogado(a).**

### 1.4 Compartilhamento (operadores/processadores)
Os dados podem ser processados por fornecedores contratados, sob **contrato de
tratamento (DPA)** e apenas para as finalidades acima:
- **Hospedagem/infraestrutura:** [Hostinger] (servidor no [país/região]).
- **E-mail transacional:** [provedor, ex. Brevo/Resend] — se ativado.
- **Mensageria (WhatsApp):** [Meta/WhatsApp Business] — se ativado.
- **Monitoramento de erros:** [Sentry] — configurado para **não** receber PII.
- **IA externa (resumo/transcrição):** [provedor de LLM] — **somente** com DPA
  assinado e consentimento específico do paciente; desligado por padrão.
Não vendemos dados. Não usamos os dados para publicidade.

### 1.5 Transferência internacional
Se algum operador processar dados fora do Brasil, informe aqui o país e a
salvaguarda adotada (cláusulas contratuais/decisão de adequação). **Verificar.**

### 1.6 Segurança
Criptografia **em repouso** dos campos sensíveis (AES-256-GCM), acesso por
autenticação, canal cifrado (HTTPS/TLS), backups e minimização (as notificações
externas não levam nome/motivo clínico). Nenhuma medida elimina 100% do risco.

### 1.7 Retenção e eliminação
Mantemos os dados pelo período necessário à finalidade e às obrigações legais
(ex.: guarda de prontuário conforme normas do CFM — **confirmar prazo**). Registros
de auditoria podem ser retidos para defesa/obrigação legal, sem conteúdo clínico.

### 1.8 Direitos do titular
O paciente pode solicitar **confirmação, acesso, correção, portabilidade, informação
sobre compartilhamento, e eliminação** (quando cabível), além de **revogar o
consentimento**. Canal: **[e-mail do DPO]**. Prazo de resposta: [15 dias].

### 1.9 Crianças e adolescentes
Se atender menores, tratar no melhor interesse e com **consentimento de um dos pais/
responsável** (art. 14). **Definir se o produto atende menores.**

---

## 2. Termo de Consentimento do Paciente (modelo)

> Apresentado ao paciente **antes** do primeiro uso; o aceite deve ser **livre,
> informado e destacado**, com data/hora registrados, e revogável a qualquer momento.

**Eu, [nome do paciente]**, declaro que fui informado(a), de forma clara, que:

1. O **Flowra Care** será usado pelo(a) meu(minha) médico(a) para me **acompanhar
   entre as consultas**, por meio de check-ins e mensagens.
2. Serão tratados **dados sobre minha saúde** (humor, sono, medicação, sintomas,
   relatos em texto/áudio, mensagens), considerados **dados sensíveis**.
3. As informações podem gerar **sinais de atenção ao meu médico**; a ferramenta
   **não faz diagnóstico** nem substitui atendimento — **em emergência devo procurar
   ajuda imediata (ex.: SAMU 192, CVV 188, pronto-socorro).**
4. Meus dados serão protegidos e compartilhados apenas com **operadores necessários**
   ao funcionamento, conforme a Política de Privacidade que me foi disponibilizada.
5. Posso **acessar, corrigir e solicitar a eliminação** dos meus dados e **revogar
   este consentimento** a qualquer momento, pelo canal **[e-mail do DPO]**, sem
   prejuízo do meu atendimento presencial.

☐ **Concordo** com o tratamento dos meus dados de saúde para o acompanhamento descrito.
☐ **(Opcional) Concordo** com o uso de **IA externa** (resumo/transcrição) que envia
   trecho do meu relato a um provedor terceiro sob contrato — *pode ser recusado sem
   prejuízo do acompanhamento*.

Paciente: __________________________  Data/hora: __________  Assinatura/aceite: ______

---

## 3. Checklist antes de atender paciente real
- [ ] Advogado(a) revisou a Política e o Termo.
- [ ] Papéis controlador/operador definidos; **DPA** assinado com cada fornecedor.
- [ ] DPO nomeado e canal de titular funcionando.
- [ ] Base legal escolhida e registrada.
- [ ] Fluxo de consentimento no app registra **aceite + data/hora + versão**.
- [ ] Limiares de risco validados por **psiquiatra**.
- [ ] Backups testados; `ENCRYPTION_KEY` em cofre.
