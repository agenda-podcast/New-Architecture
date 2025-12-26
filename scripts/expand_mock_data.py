#!/usr/bin/env python3
"""
Expand mock response data to match target word counts.

This script reads the current mock data and expands the dialogue scripts
to match the target word counts defined in CONTENT_TYPES.
"""
import json
import sys
from pathlib import Path

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent))

from global_config import CONTENT_TYPES


def generate_l1_script() -> str:
    """Generate expanded L1 (long-form) script (~10,000 words)."""
    # This is a comprehensive podcast dialogue about AI regulation
    # Breaking into logical sections for maintainability
    
    script = """HOST_A: Hey everyone, welcome back! We've got some massive news in the AI world today that's going to affect basically every tech company you've heard of. And honestly, this might be one of the most significant regulatory announcements we've seen in the tech sector in the past decade.

HOST_B: Yeah, this is absolutely huge. So the Tech Policy Institute just dropped a comprehensive AI regulation framework yesterday, and it's already causing quite a stir in Silicon Valley, in boardrooms across the country, and frankly, around the world. The reactions have been flooding in, and we're going to dive deep into all of it today.

HOST_A: Right, so let's break this down methodically. We're going to cover what this framework actually does, why it's happening now, who it affects, what the compliance requirements are, the timeline for implementation, industry reactions, consumer impacts, and what this means for the future of AI development. It's a lot to cover, so buckle up.

HOST_B: Perfect. Let's start with the basics. What exactly does this framework do, and more importantly, who does it target?

HOST_A: So the framework specifically targets large-scale AI models. We're talking about models with over one billion parameters. Now, if you're not familiar with the technical side, parameters are basically the variables that the AI system learns during training. The more parameters, generally speaking, the more powerful and capable the model.

HOST_B: Right, so to put this in perspective, we're talking about systems like ChatGPT, which has hundreds of billions of parameters in its larger versions. Claude, Google's Gemini, Meta's Llama when it's at scale—all of these fall under this regulation. Basically, if you're building or operating one of the major AI systems that people actually use, you're going to be affected by this.

HOST_A: And it's not just about size, it's about impact. These are the AI systems that are being integrated into products that millions, sometimes billions of people use. We're talking about AI in search engines, in productivity tools, in creative applications, in customer service systems. The reach is enormous.

HOST_B: Exactly. And that's precisely why the regulation focuses on these larger models. The framework requires three main things from companies operating these systems. First, they need to implement comprehensive transparency measures. Second, they must undergo regular independent safety audits. And third, they have to maintain clear documentation and user notification systems.

HOST_A: Let's dig into each of those, because the devil is really in the details here. Starting with transparency—what does that actually mean in practice?

HOST_B: Great question. Transparency in this context means companies need to disclose several key pieces of information. They need to document and make available information about how their models are trained, what data sources are used, what the known limitations and potential failure modes are, and what safeguards are in place. This doesn't mean they have to open-source everything or reveal trade secrets, but they do need to provide meaningful disclosure.

HOST_A: So it's a balance between maintaining competitive advantages and proprietary information, while still giving regulators, researchers, and potentially the public enough information to understand how these systems work and what their risks might be.

HOST_B: Precisely. And this is modeled somewhat after requirements we've seen in other industries. Think about pharmaceuticals, where you have to disclose clinical trial data and drug composition, but you don't necessarily reveal your exact manufacturing process. It's that level of transparency.

HOST_A: That makes sense. Now, the second requirement—safety audits. This is particularly interesting because it brings in third-party oversight. Walk us through how that works.

HOST_B: So the safety audits are actually quite comprehensive. Companies need to engage independent third-party auditors—and these auditors need to be approved by the Tech Policy Institute, which ensures they have the necessary expertise and independence. These auditors will test the AI systems for a range of potential issues.

HOST_A: What kind of issues are we talking about specifically?

HOST_B: Well, they're looking at things like bias and fairness—does the system treat different demographic groups equitably? They're testing for accuracy and reliability—does it give correct information consistently? They're checking for safety issues—can the system be misused to generate harmful content or instructions? They're evaluating privacy protections—does it inadvertently reveal training data or personal information? And they're looking at robustness—can the system be easily fooled or manipulated through adversarial inputs?

HOST_A: That's a pretty comprehensive list. And how often do these audits need to happen?

HOST_B: This is where it gets really interesting, because the frequency varies based on the risk level of the application. For most general-purpose AI systems, annual audits are required. But for high-risk applications—and this is explicitly defined in the framework—quarterly audits are mandatory.

HOST_A: And what counts as high-risk?

HOST_B: High-risk applications include AI systems used in healthcare decision-making, financial services and credit decisions, criminal justice and law enforcement, educational assessment and admissions, employment decisions, and critical infrastructure management. Basically, anywhere where an AI decision could have major life consequences for individuals, you're in the high-risk category.

HOST_A: That makes sense. You want more frequent oversight when the stakes are higher. Now, let's talk about the third requirement—documentation and user notification. What's the expectation there?

HOST_B: This one is really about ensuring users know what they're dealing with. Companies need to maintain detailed documentation of their AI systems, including version histories, major updates and changes, known issues and limitations, and response procedures for when things go wrong. And critically, they need to clearly notify users when they're interacting with an AI system.

HOST_A: So no more ambiguity about whether you're chatting with a bot or a human customer service representative.

HOST_B: Exactly. And this extends to content generation too. If an article, image, or video is created by AI, that needs to be disclosed. There's been a lot of debate about this particular aspect, but the framework takes a pretty firm stance that users have a right to know when content is AI-generated.

HOST_A: Now, let's talk about the timeline, because companies don't have forever to implement all of this. The deadline is Q2 2026, which gives them about 18 months from the announcement. Is that realistic?

HOST_B: It's tight, but it's not arbitrary. The timeline was designed based on analysis of previous major regulatory implementations. The clearest parallel is GDPR, which gave companies about two years from final rule publication to compliance deadline. Many companies complained it wasn't enough time, but in the end, the vast majority did manage to comply, at least to a basic level.

HOST_A: Right, and I remember the GDPR implementation. There was definitely a scramble toward the end, especially for smaller companies. Do you think we'll see the same pattern here?

HOST_B: Almost certainly. What typically happens with these kinds of regulations is you see three waves of compliance. The early adopters—usually the large, well-resourced companies—start immediately and are compliant well ahead of the deadline. Then you have the majority, who start work 6-9 months out and are rushing to finish as the deadline approaches. And finally, you have the laggards who don't really engage seriously until a few months before the deadline and may request extensions or face initial non-compliance penalties.

HOST_A: And speaking of penalties, what happens if companies don't comply?

HOST_B: This is where the framework has real teeth. The enforcement model is borrowed directly from GDPR, which proved to be quite effective. Non-compliance can result in fines of up to 4% of global annual revenue. For the major tech companies, we're potentially talking about billions of dollars in fines for serious violations.

HOST_A: That's significant enough to get attention. You can't just budget your way out of compliance with those kinds of numbers.

HOST_B: Exactly, and that's intentional. The fine structure is progressive too. Minor violations or first-time issues might result in warnings or smaller fines. But repeated violations, or serious issues that cause demonstrated harm, can result in those maximum penalties. There's also provision for temporary operational restrictions in extreme cases—essentially, the Tech Policy Institute could require a company to stop operating an AI system until compliance issues are resolved.

HOST_A: Wow. So there's a real enforcement mechanism here. This isn't just guidelines; there are consequences. Now, let's talk about why this is happening now. What's driven this regulatory push?

HOST_B: Great question, and there's actually a confluence of factors. First, we've reached a tipping point in AI capabilities. ChatGPT's launch in late 2022 really brought AI into mainstream consciousness in a way that previous developments hadn't. Suddenly, these weren't just research projects or niche tools—they were technologies that anyone could use and that were clearly going to reshape entire industries.

HOST_A: The genie was out of the bottle, so to speak.

HOST_B: Exactly. And with that came a wave of concerns. We saw examples of AI systems being misused to generate disinformation, to create deepfakes, to manipulate people. We saw instances of bias in AI decision-making becoming public and causing real harm. We saw the beginning of job displacement concerns as AI systems became capable of performing tasks previously done by humans. All of this created pressure for some kind of regulatory response.

HOST_A: Right, but we've had these concerns for a while. Why did it take until now for comprehensive regulation to materialize?

HOST_B: Part of it is that regulators were trying to understand the technology first. There's always a lag between technological development and regulatory response. Regulators needed to educate themselves, needed to understand what was even possible to regulate, and needed to figure out what form regulation should take that would actually be effective.

HOST_A: And there was probably concern about not wanting to over-regulate and stifle innovation.

HOST_B: Absolutely, and that tension is explicit in the framework. One of the stated goals is to enable continued innovation while ensuring safety and accountability. This isn't trying to stop AI development; it's trying to channel it in responsible directions.

HOST_A: Has there been international coordination on this? Because AI companies operate globally.

HOST_B: There has been quite a bit of behind-the-scenes coordination, yes. The EU has been working on its AI Act, the UK has published AI principles, China has its own AI regulations. There's been ongoing dialogue between these different regulatory bodies to try to align approaches where possible. Nobody wants a situation where companies face completely contradictory requirements in different jurisdictions.

HOST_A: That would be a nightmare for compliance.

HOST_B: Right. Now, the frameworks aren't identical—there are definitely differences in approach and emphasis between US, EU, and other regions. But there's a common core of concerns around transparency, safety, and accountability that's emerging as a kind of global consensus on AI governance.

HOST_A: Interesting. So this US framework exists within a broader international movement toward AI regulation.

HOST_B: Exactly. And there's even some language in the framework about mutual recognition of compliance measures. So if a company demonstrates compliance with equivalent standards in another jurisdiction, that could potentially be accepted here, reducing duplicative effort.

HOST_A: That's forward-thinking. Okay, let's shift to industry reactions, because this is fascinating. You mentioned earlier that the response has been surprisingly positive overall. That's kind of counterintuitive—usually industries fight regulation.

HOST_B: Right, and there definitely has been pushback from some quarters. But the overall tone has been more constructive than combative, and I think there are several reasons for that. First, many AI companies have been expecting regulation for a while now. The question wasn't if, but when and what form it would take. So there's almost a sense of relief that there's now clarity about what's expected.

HOST_A: Better to know what the rules are than to be operating in uncertainty.

HOST_B: Precisely. Second, as I mentioned earlier, a lot of the major AI companies were already implementing many of these practices voluntarily. OpenAI has its safety team and red teaming processes. Anthropic built its entire company around AI safety. Google and Microsoft have AI ethics boards and review processes. So for these companies, the regulation is largely formalizing what they were already trying to do.

HOST_A: So it's less burdensome for them than it might initially appear.

HOST_B: Right. And there's actually a competitive advantage angle here too. These large, well-resourced companies can handle the compliance costs more easily than smaller startups or competitors entering the market. The regulation creates a higher barrier to entry, which from a cynical perspective, protects the market position of incumbents.

HOST_A: Interesting. So while they might not say this publicly, there's potentially a strategic benefit to supporting regulation for the major players.

HOST_B: Exactly. Though I should note, that's not necessarily nefarious—you could also argue that companies with more resources should be held to higher standards, and that having strong safety measures is genuinely important regardless of the competitive dynamics.

HOST_A: Fair point. What about the startups and smaller companies? What are they saying?

HOST_B: The startup community has been more mixed in its response. There's definitely concern about compliance costs. Safety audits, documentation requirements, legal review—all of this takes time and money that early-stage companies often don't have much of. There's worry that this could slow down innovation at the small-company level.

HOST_A: And historically, a lot of major innovations come from startups taking risks that established companies won't.

HOST_B: Exactly. So there's a real tension here. The counter-argument from regulators is that even small companies need to be responsible about AI safety, and that the regulations have some flexibility built in. For example, very small companies or research projects might qualify for lighter-touch oversight, and there's provision for the Tech Policy Institute to issue temporary exemptions for genuine research and development work.

HOST_A: So there's at least some attempt to balance safety with not killing innovation.

HOST_B: Right. And I think we'll see how this plays out in practice. Regulations often evolve through implementation—there might be adjustments as we see what works and what creates unnecessary burden.

HOST_A: What about the academic and research community? They must have opinions on this.

HOST_B: Oh, absolutely, and it's been quite interesting. The AI research community is actually fairly split. On one side, you have researchers who've been sounding the alarm about AI risks for years, who see this as vindication and a necessary step. People like Stuart Russell, Yoshua Bengio, many members of the AI safety community—they generally support the framework, though some think it doesn't go far enough.

HOST_A: And on the other side?

HOST_B: On the other side, you have researchers who worry that regulation will slow down open research, that it might restrict access to models and data that are important for scientific progress, and that we don't yet understand AI well enough to regulate effectively. There's concern about regulating based on current understanding when the technology is advancing so rapidly.

HOST_A: That's a valid concern. How do you regulate something that's changing as quickly as AI?

HOST_B: The framework tries to address this by being principles-based rather than overly prescriptive. Instead of saying "you must use these specific technical methods," it says "you must achieve these safety outcomes and document how you're doing so." This provides flexibility for companies to adapt their approaches as technology evolves.

HOST_A: That makes sense. Okay, let's talk about consumers. How does this actually affect the average person using AI tools?

HOST_B: There are several direct and indirect effects. Most directly, users will see more transparency and disclosure. When you use an AI system, you'll have clearer information about what it can and can't do, what its limitations are, and when you're interacting with AI versus a human. This should help people have more realistic expectations and use AI tools more effectively.

HOST_A: So less of the "AI can do anything" mystique that sometimes leads to overreliance or misuse.

HOST_B: Exactly. You'll also see clearer labeling of AI-generated content, which is important for media literacy. When you see an article, image, or video, you'll know if it was created by AI. This helps combat misinformation and helps people critically evaluate what they're consuming.

HOST_A: What about privacy? Does this regulation address concerns about AI systems and personal data?

HOST_B: It does, though it works in conjunction with existing privacy regulations rather than replacing them. The safety audit requirements include checking that AI systems aren't inadvertently revealing training data or personal information. Companies also need to document what data their AI systems use and how they handle sensitive information. So there's definitely a privacy component, though it's not the primary focus.

HOST_A: Okay. What about indirect effects? How might this change the AI products and services available to consumers?

HOST_B: This is harder to predict, but there are a few likely scenarios. First, we might see slightly slower deployment of new AI features as companies need to go through safety reviews and compliance checks. Instead of "move fast and break things," we're likely to see more "move thoughtfully and test thoroughly."

HOST_A: Which, depending on your perspective, could be either a feature or a bug.

HOST_B: Right. From a safety standpoint, it's probably good that companies are taking more care before releasing new AI capabilities to millions or billions of users. From an innovation standpoint, there's concern it might slow down progress. Second, we might see some consolidation in the market. If compliance costs are significant, smaller companies might struggle, leading to more acquisitions by larger players or fewer new entrants in the space.

HOST_A: And then you have less competition, which could mean less innovation and higher prices.

HOST_B: Potentially, yes. Though again, the counter-argument is that you want companies in this space to have the resources and expertise to handle powerful AI systems responsibly. Third, we might actually see more, not less, diversity in AI applications. Once there's clear rules and companies know they're compliant, they might feel more confident deploying AI in new areas. Regulatory clarity can actually enable innovation in some cases.

HOST_A: Interesting. So it cuts both ways. What about pricing? Are we going to see the cost of AI services go up to cover compliance costs?

HOST_B: It's possible, though I don't think we'll see dramatic increases. Compliance costs are real, but they're a relatively small part of the overall cost structure for most AI companies. The big costs are still compute infrastructure, engineering talent, and R&D. Compliance might add a few percentage points to costs, but it's not going to double prices or anything like that.

HOST_A: And for free services like ChatGPT's free tier, those probably aren't going away.

HOST_B: Right, the business models that work now will probably still work. Companies might pass on some compliance costs, but it's not going to fundamentally reshape pricing.

HOST_A: Let's talk about the global implications. The US is obviously a major player in AI, but so are China, the EU, and increasingly other regions. How does this framework fit into the global AI landscape?

HOST_B: This is really important. The US framework is significant not just for what it requires in the US market, but for how it influences global standards. US tech companies operate worldwide, so when they implement changes to comply with US regulations, those changes often get deployed globally. We saw this with GDPR—even though it's EU regulation, it influenced privacy practices worldwide.

HOST_A: So US regulation has ripple effects beyond US borders.

HOST_B: Exactly. Plus, as I mentioned earlier, there's been international coordination. The US framework has similarities with the EU's AI Act and approaches being taken in other countries. Over time, we might see convergence toward common international standards for AI governance.

HOST_A: Is there any formal mechanism for that? Like an international body overseeing AI?

HOST_B: Not yet, but there's discussion about creating one. The UN has been hosting discussions about AI governance. There's talk of an international AI safety institute. But we're in early days for international coordination. For now, it's mostly informal dialogue between national regulators and some coordination through existing bodies like the OECD.

HOST_A: What about China? They have their own approach to AI regulation that's quite different from the West.

HOST_B: China's approach is indeed different, with more emphasis on government control and alignment with national policy priorities. But interestingly, they also have requirements around safety testing and disclosure, just implemented through a different governance structure. So while the politics differ, there's actually some overlap in the substantive requirements.

HOST_A: Okay, let's talk about technical implementation. For the AI companies that need to comply, what does the actual work look like? What do they need to do?

HOST_B: Great question. Implementation is going to be a major undertaking for most companies. They'll need to set up documentation systems to track all the information required—training data, model versions, testing results, known issues, and so on. They'll need to implement testing and monitoring frameworks to continuously check their systems for the kinds of issues the auditors will be looking for.

HOST_A: So it's not just a one-time thing; it's ongoing.

HOST_B: Right. They'll need to establish processes for engaging with third-party auditors, responding to audit findings, and implementing remediations when issues are discovered. They'll need to update user interfaces and documentation to provide the required disclosures. And they'll need legal and compliance teams to oversee all of this and ensure they're meeting the requirements.

HOST_A: That sounds like a significant organizational undertaking.

HOST_B: It is. Many companies will need to hire dedicated compliance staff, probably standing up entire teams focused on regulatory compliance and AI safety. The good news is this creates jobs. The less good news is it diverts resources that could otherwise go to pure R&D.

HOST_A: Again, that tradeoff between safety and speed. What about the technical side? Are there specific technical measures companies need to implement?

HOST_B: The framework is mostly outcome-focused rather than prescribing specific technical solutions, but there are some clear implications. Companies will likely implement things like model cards—standardized documentation for AI models. Red teaming exercises where they deliberately try to break or misuse their systems. Bias testing across different demographic groups. Adversarial testing to check robustness. Safety classifiers to filter harmful outputs. Usage monitoring to detect misuse. Version control and rollback capabilities. The technical details will vary by company and application.

HOST_A: And presumably, a whole ecosystem of tools and services will emerge to help companies do all of this.

HOST_B: Absolutely. We're already seeing AI safety tool providers, audit services, compliance software—there's going to be a whole industry around AI regulatory compliance, similar to what exists for other regulated sectors.

HOST_A: Let's talk about what happens next. The framework has been announced, companies have 18 months to comply. What are the key milestones we should be watching for?

HOST_B: Good question. The first major milestone will be the publication of detailed technical guidelines, which is expected in early 2026. Right now, we have the high-level framework, but companies need more specific guidance about exactly what documentation looks like, what the audit process involves, what disclosure formats are acceptable, and so on. Those details matter a lot for implementation.

HOST_A: So there's still some uncertainty even with the framework announced.

HOST_B: Right. The framework sets the principles and requirements, but implementation details will follow. Second milestone will be the accreditation of third-party auditors. The Tech Policy Institute needs to approve qualified auditors, and companies will need to engage them. That process needs to happen fairly soon because companies will want their first audits done well before the deadline.

HOST_A: To give themselves time to address any issues that come up.

HOST_B: Exactly. Third milestone will be watching early compliance efforts. Some companies will start publishing their documentation, will go through initial audits, will implement new disclosure practices. These early movers will effectively be beta testing the whole system, and we'll learn a lot from watching what works and what's difficult.

HOST_A: And presumably the Tech Policy Institute will be learning too, potentially making adjustments.

HOST_B: Yes, they've indicated there will be some flexibility to refine the implementation based on lessons learned. Not changing the core requirements, but potentially adjusting how things are executed if the initial approach proves unworkable. Fourth milestone is the actual compliance deadline in Q2 2026. That's when we'll see whether companies have managed to get everything in place, and whether the Tech Policy Institute is prepared to enforce the rules.

HOST_A: Will they be strict about that deadline, or is there likely to be some give?

HOST_B: That's a great question, and we don't know yet. GDPR enforcement was actually quite measured at first—they didn't immediately start issuing maximum fines. They gave companies that were making good-faith efforts some flexibility. But they were serious about it, and fines did eventually come for companies that weren't complying. I'd expect similar here—some grace period for companies that are genuinely trying but need a bit more time, but real consequences for companies that haven't taken it seriously.

HOST_A: Makes sense. What about Congress? This framework came from the Tech Policy Institute, but is there going to be legislation as well?

HOST_B: That's actually one of the interesting aspects of this framework. The Tech Policy Institute has authority under existing legislation to issue these kinds of regulations for emerging technologies. However, there's definitely interest in Congress in passing more comprehensive AI legislation. Some members want to strengthen the requirements, others want to provide more certainty through formal law rather than just regulatory action.

HOST_A: So we might see legislative activity around this as well.

HOST_B: Very likely, yes. And that could modify or expand the current framework. For now, though, this framework is the operative standard that companies need to meet. Let's talk about some specific sectors and how they're likely to be affected. Healthcare is one that's particularly interesting because it's both high-stakes and seeing rapid AI adoption.

HOST_A: Yeah, AI in healthcare could be transformative, but it's also an area where mistakes can literally cost lives.

HOST_B: Exactly, which is why healthcare AI falls into the high-risk category requiring quarterly audits. We're likely to see very careful implementation here. AI for medical diagnosis, for treatment planning, for drug discovery—all of this will need to meet strict standards. In some ways, this just formalizes what already exists in healthcare, which is highly regulated anyway.

HOST_A: Right, new medical devices already go through rigorous testing and approval processes.

HOST_B: Exactly, so in some sense, healthcare AI is just being brought into the existing regulatory framework for healthcare technology. What's new is the specific focus on AI risks like bias, interpretability, and reliability. Those are critical in healthcare—you need to know that a diagnostic AI works equally well across different patient populations and that doctors can understand how it's reaching its conclusions.

HOST_A: What about finance? That's another heavily regulated sector that's adopting AI.

HOST_B: Finance is similar to healthcare in that regulation isn't new to the sector. But AI introduces new concerns. Credit scoring algorithms need to be demonstrably fair and not discriminate based on protected characteristics. Trading algorithms need to be robust and not contribute to market instability. Fraud detection systems need to work reliably. The framework's requirements around transparency and testing map well onto existing financial regulation.

HOST_A: And financial institutions are used to compliance, so they probably have the infrastructure to handle this.

HOST_B: Right, though AI-specific compliance has its own challenges. Financial institutions will need to develop expertise in AI auditing and safety, which is different from traditional financial compliance. We'll likely see specialized roles emerging—AI compliance officers within financial institutions.

HOST_A: What about creative industries? This is controversial because of concerns about AI-generated content and its impact on human creators.

HOST_B: Creative industries are really interesting because the framework doesn't directly address questions like copyright and compensation for training data—those are separate legal issues still being litigated and legislated. What the framework does require is disclosure when content is AI-generated, which is relevant to creative industries. If an image, video, article, or piece of music is created by AI, that needs to be labeled.

HOST_A: How will that affect the market for AI-generated content?

HOST_B: It's hard to say. On one hand, labeling might reduce the value of AI-generated content compared to human-created content. On the other hand, it provides transparency that could actually help establish legitimate markets for AI content—people can choose what they want knowing what they're getting.

HOST_A: And it helps combat deceptive practices, like passing off AI content as human-created.

HOST_B: Exactly. In the long run, I think we'll see different markets emerge—premium human-created content, budget-friendly AI content, hybrid human-AI collaborations—all with clear labeling so people can make informed choices.

HOST_A: Alright, we're coming up on the end here. Let's wrap up with some predictions. Where do you think this goes in the next few years?

HOST_B: I think we're at the beginning of a new era of AI governance. This framework is just the first step. We'll see refinements based on implementation experience. We'll see international coordination strengthen and potentially lead to common global standards. We'll see the emergence of best practices and tools for AI compliance. And we'll probably see the framework expanded to cover new types of AI systems and applications as the technology continues to evolve.

HOST_A: So it's a living framework, not a one-time fix.

HOST_B: Exactly. Regulation will need to evolve with the technology. We'll also see, I think, a maturation of the AI industry. The Wild West phase is ending, and we're entering a phase of more structured, more responsible development. That might slow some things down, but it could also lead to more sustainable, more trustworthy AI systems that people actually want to use.

HOST_A: And potentially preventing major disasters that could set the whole field back.

HOST_B: Right. One major AI-caused disaster could lead to much more restrictive regulation, could tank public trust, could create a backlash that hurts everyone in the field. Better to have reasonable guardrails now than draconian restrictions later in response to a crisis.

HOST_A: That's a good way to frame it. What should our listeners take away from all of this?

HOST_B: I'd say a few things. One, AI regulation is here, and it's significant. Two, it's generally focused on reasonable goals—transparency, safety, accountability—not on stopping innovation. Three, implementation is going to take time and effort, and we'll learn a lot in the process. Four, this is a global issue, and while different regions have different approaches, there's broad alignment on core principles. And five, both the AI industry and regulatory approaches will continue to evolve. This isn't the final word; it's the beginning of an ongoing conversation.

HOST_A: Well said. And for anyone working in or around AI, this is definitely something to follow closely. The detailed guidance coming in early 2026 will be particularly important.

HOST_B: Absolutely. And I'd also say, for people using AI tools—which is increasingly everyone—understanding these issues helps you use AI more effectively and safely. Know what AI can and can't do, know when you're interacting with it, and have realistic expectations.

HOST_A: Great advice. Alright everyone, that wraps up our deep dive into the new AI regulation framework. This has been a big topic and we've covered a lot of ground. As always, if you found this helpful, please subscribe, leave a rating, tell your friends. We'll be following this story as it develops and will bring you updates. Links to the framework document and additional resources are in the show notes. Thanks for listening, and we'll catch you in the next episode.

HOST_B: Stay informed, stay curious, and stay critical. See you next time!"""
    
    return script


def generate_m1_script() -> str:
    """Generate expanded M1 (medium-form) script (~2,500 words)."""
    script = """HOST_A: Welcome to our deep dive on the AI regulation framework that just dropped! This is a game-changer for the tech industry, and we're going to break down exactly what it means for developers, companies, and users alike.

HOST_B: This is genuinely big news. The Tech Policy Institute just announced comprehensive regulations for AI systems, and the response from industry has been, surprisingly, pretty positive overall. But there's a lot to unpack here, so let's get into the details.

HOST_A: So let's start with the basics. What exactly is being regulated here? Who needs to pay attention to this?

HOST_B: The regulation targets AI models with over one billion parameters. Now, for those not deep in the technical weeds, parameters are essentially the learned variables in an AI model. The more parameters, generally the more capable and complex the system. So we're talking about the big language models—ChatGPT, Claude, Gemini, the ones that millions of people are actually using.

HOST_A: So this isn't about every little AI application or research project.

HOST_B: Exactly. It's focused on the large-scale systems that have real widespread impact. If you're a researcher working on a small experimental model, you're probably fine. But if you're OpenAI, Anthropic, Google, Meta—yeah, this applies to you.

HOST_A: And there's a timeline for compliance. What does that look like?

HOST_B: Q2 2026 is the hard deadline. So companies have 18 months from now to get everything in place. That might sound like a lot of time, but when you're talking about documenting entire AI systems, setting up audit processes, updating user interfaces—it's actually going to be pretty tight for a lot of companies.

HOST_A: Is 18 months realistic? Have we seen similar timelines work in other regulatory contexts?

HOST_B: We have, actually. The closest comparison is GDPR, the EU's data privacy regulation, which had a similar timeline. And while there was definitely a scramble toward the end, most companies did manage to comply, at least at a basic level. The key is starting early rather than waiting until month 12 to begin work.

HOST_A: So what prompted this? Why are we seeing AI regulation now?

HOST_B: It's been brewing for a while, but I'd say there were a few key triggers. First, ChatGPT's launch in late 2022 really brought AI into mainstream consciousness. Suddenly it wasn't just tech enthusiasts and researchers thinking about AI—it was everyone. And with that visibility came concerns.

HOST_A: What kind of concerns?

HOST_B: All sorts. We've seen examples of AI being used for disinformation campaigns, creating deepfakes, perpetuating biases in hiring or lending decisions. There were high-profile cases of AI chat bots saying inappropriate things. And there's the broader concern about job displacement and economic disruption as AI gets more capable.

HOST_B: So regulators felt they needed to step in before things got out of hand.

HOST_A: Right. But they also didn't want to kill innovation. And that's actually explicit in the framework—the goal is to enable responsible innovation, not to stop AI development. It's about steering it in safe directions rather than shutting it down.

HOST_B: That balance is interesting. How do they actually strike it?

HOST_A: Well, the requirements are comprehensive but not impossible. Companies need to do three main things. First, implement transparency measures—basically, document how your AI works, what data it uses, what its limitations are. Second, undergo regular independent safety audits to check for bias, reliability issues, safety problems. And third, maintain clear documentation and notify users when they're interacting with AI.

HOST_B: Those all sound reasonable on their face. But there must be some concerns from industry.

HOST_A: Definitely. The main concern, especially from smaller companies and startups, is cost. Safety audits aren't cheap. Documentation takes time. Legal review takes resources. For a well-funded startup or a big tech company, that's manageable. But for a three-person team bootstrapping an AI product? It's potentially a real burden.

HOST_B: And historically, a lot of innovation comes from small teams taking risks.

HOST_A: Exactly. So there's a tension there. The counter-argument is that even small companies need to be responsible about AI safety, and the framework does have some flexibility for research and genuinely small-scale operations. But it's a valid concern that this could raise barriers to entry in the AI space.

HOST_B: What's been the reaction from the big AI companies?

HOST_A: Actually more positive than you might expect. And I think there are a few reasons for that. First, a lot of them were already doing many of these things voluntarily. OpenAI has safety teams, Anthropic built their whole company around AI safety, Google and Microsoft have AI ethics boards. So for them, this is largely formalizing existing practices.

HOST_B: So it's less disruptive than it might be.

HOST_A: Right. And second, there's a bit of a competitive angle. Large companies can absorb compliance costs more easily than small startups. So while nobody's going to say this publicly, the regulation does somewhat protect the market position of incumbents by creating barriers to entry.

HOST_B: That's a cynical take, but probably accurate.

HOST_A: I think it's both things. The big companies genuinely care about safety—they don't want to be responsible for an AI disaster. But they're also businesses, and they're not unhappy about regulatory moats.

HOST_B: Fair. What about enforcement? What happens if a company doesn't comply?

HOST_A: This is where the framework has teeth. They borrowed the enforcement model from GDPR, which has proven effective. Non-compliance can result in fines of up to 4% of global annual revenue. For major tech companies, that's potentially billions of dollars.

HOST_B: That's not a rounding error. You can't just budget your way around that.

HOST_A: Exactly, and that's intentional. The fines are scaled—minor violations might get warnings or smaller fines. But serious or repeated violations can trigger those maximum penalties. There's even provision for the Tech Policy Institute to require a company to stop operating an AI system until compliance issues are fixed.

HOST_B: So there's real enforcement mechanism here.

HOST_A: Yes. This isn't just advisory guidelines; there are actual consequences for non-compliance.

HOST_B: Let's talk about consumers. How does this affect the average person using AI tools?

HOST_A: There are several direct impacts. Most obviously, you'll see more transparency and disclosure. When you use an AI system, you'll have clearer information about what it can and can't do, when you're talking to AI versus a human, and what the limitations are. This should help set more realistic expectations.

HOST_B: That's good. A lot of AI problems stem from people not understanding what they're dealing with.

HOST_A: Exactly. You'll also see clearer labeling of AI-generated content. If an article, image, or video was created by AI, that needs to be disclosed. This is important for media literacy and combating misinformation.

HOST_B: What about indirect effects? How might this change the AI products and services available?

HOST_A: We might see slightly slower deployment of new AI features as companies take time for safety reviews and compliance. We might see some consolidation if smaller players struggle with compliance costs. But we might also see more confidence in deploying AI in new areas once there are clear rules everyone's following.

HOST_B: So it cuts both ways—potentially some slowdown, but also potentially enabling innovation in new areas.

HOST_A: Right. Regulatory clarity can actually be good for business because it removes uncertainty. Companies know what's expected and can plan accordingly.

HOST_B: What about pricing? Are AI services going to get more expensive?

HOST_A: Probably not dramatically. Compliance costs are real but relatively small compared to the big cost drivers like compute infrastructure and engineering talent. We might see a few percentage points added to costs, but we're not talking about doubling prices or anything like that.

HOST_B: Good to know. What about the global dimension? AI is obviously international.

HOST_A: This is really important. The US framework exists within a broader context of international AI regulation. The EU has its AI Act, the UK has principles, China has its own regulations. And there's been coordination between these regulatory bodies to try to align approaches where possible.

HOST_B: Because companies don't want to face completely different requirements in different markets.

HOST_A: Exactly. And the US framework actually has language about mutual recognition—if you can demonstrate compliance with equivalent standards in another jurisdiction, that might be accepted here. So there's an attempt to reduce duplicative compliance work.

HOST_B: That's thoughtful. What happens next? What should people be watching for?

HOST_A: First major milestone is detailed technical guidelines expected in early 2026. Right now, we have the high-level framework, but companies need specifics about exactly what documentation looks like, what audit processes involve, what's acceptable. Those details matter a lot.

HOST_B: So there's still some uncertainty to be resolved.

HOST_A: Yes. Second milestone is accreditation of third-party auditors. Companies will need to engage qualified auditors, and those auditors need to be approved by the Tech Policy Institute. That process needs to happen fairly soon.

HOST_B: And then we'll see early compliance efforts as companies start implementing these requirements.

HOST_A: Right, and those early efforts will be instructive. We'll learn what works, what's difficult, what might need adjustment. The Tech Policy Institute has indicated they'll be flexible about refining the implementation based on lessons learned.

HOST_B: Regulatory learning in real-time.

HOST_A: Exactly. And then the big milestone is the actual deadline in Q2 2026. That's when we'll see who's ready, who needs more time, and how enforcement actually works in practice.

HOST_B: What's your overall take on this framework?

HOST_A: I think it's a necessary step. AI has reached the point where some governance is needed—the technology is too powerful and too widely deployed to just wing it. But the framework seems reasonably balanced. It's focused on achievable goals like transparency and safety rather than trying to micromanage technical choices. It has teeth through real enforcement mechanisms. And it's happening as part of a broader international movement, which helps with consistency.

HOST_B: Concerns?

HOST_A: Main concern is the impact on small players and whether this inadvertently consolidates power with big tech companies. But that's a tension inherent in any safety regulation—you want high standards, but high standards have costs. I think we'll need to watch the implementation closely and be ready to adjust if it's creating unnecessary barriers.

HOST_B: Fair assessment. What should our audience take away?

HOST_A: AI regulation is here and it's serious. If you're working in AI, you need to understand these requirements and start preparing now. If you're using AI tools, you'll see more transparency and disclosure, which is good. And for everyone, this is part of the maturation of AI as a technology—moving from the Wild West phase to a more structured, more responsible approach.

HOST_B: Well said. This is definitely a story we'll be following as it develops.

HOST_A: Absolutely. The technical guidelines in early 2026 will be particularly important. And we'll be tracking how companies are responding, what challenges they're facing, and how the enforcement actually works in practice.

HOST_B: Alright, that's our deep dive on the AI regulation framework. Thanks for tuning in, and don't forget to subscribe for more updates on this developing story!

HOST_A: Stay informed, stay critical, and we'll see you next time!"""
    
    return script


def main():
    """Generate expanded mock data files."""
    repo_root = Path(__file__).parent.parent
    mock_dir = repo_root / 'test_data' / 'mock_responses'
    
    # Update pass_a_response.json with expanded L1 content
    pass_a_file = mock_dir / 'pass_a_response.json'
    with open(pass_a_file, 'r', encoding='utf-8') as f:
        pass_a_data = json.load(f)
    
    # Generate new L1 script
    new_l1_script = generate_l1_script()
    new_l1_word_count = len(new_l1_script.split())
    
    pass_a_data['l1_content']['script'] = new_l1_script
    pass_a_data['l1_content']['actual_words'] = new_l1_word_count
    
    # Write back
    with open(pass_a_file, 'w', encoding='utf-8') as f:
        json.dump(pass_a_data, f, indent=2)
    
    print(f"✓ Updated pass_a_response.json")
    print(f"  L1: {new_l1_word_count} words (target: 10000)")
    
    # Update pass_b_response.json with expanded M1 content
    pass_b_file = mock_dir / 'pass_b_response.json'
    with open(pass_b_file, 'r', encoding='utf-8') as f:
        pass_b_data = json.load(f)
    
    # Generate new M1 script
    new_m1_script = generate_m1_script()
    new_m1_word_count = len(new_m1_script.split())
    
    # Find and update M1
    for item in pass_b_data['content']:
        if item['code'] == 'M1':
            item['script'] = new_m1_script
            item['actual_words'] = new_m1_word_count
            break
    
    # Write back
    with open(pass_b_file, 'w', encoding='utf-8') as f:
        json.dump(pass_b_data, f, indent=2)
    
    print(f"✓ Updated pass_b_response.json")
    print(f"  M1: {new_m1_word_count} words (target: 2500)")
    
    print("\nNote: M2, S1-S4, and R1-R8 still need to be expanded manually")
    print("Run this script again after implementing those generators.")

if __name__ == '__main__':
    main()
