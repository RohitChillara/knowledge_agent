import spacy


class Extraction:
    nlp=spacy.load("en_core_web_lg")
    def __init__(self,text):
        self.text=text

    def subject_extraction(self):
        doc=Extraction.nlp(self.text)
        subjects=set()
        subject_tokens=set()
        subject=None
        for token in doc:
            #print(token.text, token.pos_)
            print(token.text, token.dep_, token.head.text)
            if((token.dep_=="nsubj" or token.dep_=="nsubjpass") and (token.pos_!="PRON" and token.pos_!="NUM")):
                subject=token.text
                for ent in doc.ents:
                    if(ent.start<=token.i<ent.end):
                        subject=ent.text        
                subjects.add(subject)
                subject_tokens.add(token)
                #print(subject_tokens)
            elif((token.dep_=="conj" or token.dep_=="appos") and (token.pos_!="PRON" and token.pos_!="NUM")):
                subject=token.text
                if(token.head in subject_tokens):
                    for ent in doc.ents:
                        if(ent.start<=token.i<ent.end):
                            subject=ent.text
                    subjects.add(subject)
                    subject_tokens.add(token)
        #print(subjects)

    def object_extraction(self):
        doc=Extraction.nlp(self.text)
        for ent in doc.ents:
            print(ent.text, ent.label_)


        
test="""Karthaveer Reddy, Rohit Chillara, and Elena Petrova are currently enrolled at
the University of Stuttgart. A research paper was published by the team
last year. The degree requires several years of dedicated study. She is
pursuing a PhD in mechanical engineering. Google was founded in California.
"""

test2="""Dr. Amara Okafor and her colleague, Professor Liu Wei, published a paper on
renewable energy in Nature last month. The paper, which took three years to
complete, was funded by the European Research Council. Neither the
university nor the government initially supported the project. Okafor,
who previously worked at MIT, is now leading a new lab in Berlin. Her lab
studies both solar efficiency and battery storage, and it has already
attracted several PhD candidates.
"""

test3="He, who studies mechanical engineering, also teaches part-time."

test4="""Dr. Maria Santos, a physicist, and her students, Tom Baker and Priya Nair,
published a study last spring. The study, which examined climate patterns
across three continents, was funded by both the National Science
Foundation and a private donor. Either the university or the ministry will
host next year's conference. Santos, who leads the climate research group,
previously worked at Stanford before moving to Oslo. A committee reviewed
the proposal, and it approved additional funding. The lab, together with
its partner institution, is expanding into new research areas.There were three researchers, 
including Santos and her colleague Baker, who contributed significantly to the project; one of them later became the
lab's director.
"""

test5="""There were three researchers, including Santos and her colleague Baker, who
contributed significantly to the project; one of them later became the
lab's director.
"""



# my_obj=Extraction("Elena Petrova is currently studying at the Technical University of Munich.")
# my_obj.object_extraction()
nlp=spacy.load("en_core_web_lg")
doc = nlp("The team reviewed the results of the experiment.")
for ent in doc.ents:
    print(ent.text, ent.label_)
